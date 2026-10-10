"""Per-bill orchestration: extract -> normalize -> validate (re-read once) -> facts -> stats -> answers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from . import prompts
from .llm import LLMClient
from .normalize import normalize_l1
from .preprocess import load_image_bytes
from .schema import empty_l1, provider_from_bill_id
from .stats import compute_stats
from .validate import check_l1

log = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "I could not reliably read the information needed for this question from the bill, "
    "so I cannot give a confident answer."
)


@dataclass
class BillResult:
    bill_id: str
    l1: dict
    issues: list[str] = field(default_factory=list)
    raw_l1: dict | None = None
    facts: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    answers: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def debug(self) -> dict:
        return {
            "bill_id": self.bill_id, "l1": self.l1, "issues": self.issues, "raw_l1": self.raw_l1,
            "facts": self.facts, "stats": self.stats, "answers": self.answers, "errors": self.errors,
        }


class BillDecoder:
    def __init__(self, client: LLMClient, max_image_side: int = 2000, fewshot_image: Path | None = None):
        self.client = client
        self.max_side = max_image_side
        self.fewshot = load_image_bytes(fewshot_image, max_image_side) if fewshot_image and fewshot_image.exists() else None

    # ----- Level 1
    def extract_l1(self, image: bytes, bill_id: str) -> tuple[dict, dict, list[str]]:
        provider = provider_from_bill_id(bill_id)
        images = [self.fewshot, image] if self.fewshot else [image]
        prompt = prompts.l1_prompt(provider)
        if self.fewshot:
            prompt = "The FIRST image is the worked-example bill; extract from the SECOND image.\n\n" + prompt

        raw = self.client.json_call(prompt, images, tag=f"l1_{bill_id}")
        rec = normalize_l1(raw, bill_id)
        issues = check_l1(rec)
        if issues:
            log.info("%s: %d check(s) failed, re-reading: %s", bill_id, len(issues), issues)
            try:
                raw2 = self.client.json_call(prompts.l1_reread_prompt(provider, raw, issues), images,
                                             tag=f"l1re_{bill_id}")
                rec2 = normalize_l1(raw2, bill_id)
                issues2 = check_l1(rec2)
                if len(issues2) <= len(issues):
                    raw, rec, issues = raw2, rec2, issues2
            except Exception as exc:  # keep first reading
                log.warning("%s: re-read failed: %s", bill_id, exc)
        return rec, raw, issues

    # ----- Level 2
    def extract_facts(self, image: bytes, bill_id: str) -> dict:
        return self.client.json_call(prompts.facts_prompt(provider_from_bill_id(bill_id)), [image],
                                     tag=f"facts_{bill_id}")

    def answer(self, image: bytes, res: BillResult, questions: list[tuple[str, str]]) -> dict[str, str]:
        if not questions:
            return {}
        data = self.client.json_call(prompts.l2_prompt(res.l1, res.facts, res.stats, questions), [image],
                                     tag=f"l2_{res.bill_id}")
        answers = data.get("answers", data)
        out = {}
        for qid, _ in questions:
            a = answers.get(qid) if isinstance(answers, dict) else None
            out[qid] = " ".join(str(a).split()) if a and str(a).strip() else FALLBACK_ANSWER
        return out

    # ----- full bill
    def process(self, path: Path, questions: list[tuple[str, str]] | None = None, level: str = "all") -> BillResult:
        bill_id = path.stem
        res = BillResult(bill_id=bill_id, l1=empty_l1(bill_id))
        try:
            image = load_image_bytes(path, self.max_side)
        except Exception as exc:
            res.errors.append(f"image: {exc}")
            res.answers = {qid: FALLBACK_ANSWER for qid, _ in questions or []}
            return res

        try:
            res.l1, res.raw_l1, res.issues = self.extract_l1(image, bill_id)
        except Exception as exc:
            log.error("%s: Level 1 failed: %s", bill_id, exc)
            res.errors.append(f"l1: {exc}")

        if level in ("all", "2") and questions:
            try:
                res.facts = self.extract_facts(image, bill_id)
            except Exception as exc:
                log.warning("%s: facts failed: %s", bill_id, exc)
                res.errors.append(f"facts: {exc}")
            try:
                res.stats = compute_stats(res.l1, res.facts)
            except Exception as exc:
                log.warning("%s: stats failed: %s", bill_id, exc)
                res.errors.append(f"stats: {exc}")
            try:
                res.answers = self.answer(image, res, questions)
            except Exception as exc:
                log.error("%s: answers failed: %s", bill_id, exc)
                res.errors.append(f"l2: {exc}")
                res.answers = {qid: FALLBACK_ANSWER for qid, _ in questions}
        return res
