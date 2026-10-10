"""Streamlit UI for the Utility Bill Decoder.  Run:  streamlit run app.py

Same pipeline as the CLI (decoder.pipeline.BillDecoder) — the UI only displays results.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from decoder.__main__ import main as cli_main
from decoder.config import ConfigError, load_settings
from decoder.io_csv import l1_to_cell
from decoder.llm import LLMClient
from decoder.pipeline import BillDecoder
from decoder.preprocess import load_image_bytes
from decoder.prompts import SAMPLE_QA
from decoder.stats import compute_stats

st.set_page_config(page_title="Utility Bill Decoder", page_icon="⚡", layout="wide")

TYPE_LABELS = {
    "energy": "Energy", "fixed": "Fixed charges", "fpa": "Fuel price adjustment", "quarterly_adjustment":
    "Quarterly adjustment", "surcharge": "Surcharge", "meter_rent": "Meter rent", "subsidy": "Subsidy",
    "other": "Other", "gst": "Sales tax (GST)", "electricity_duty": "Electricity duty", "income_tax": "Income tax",
    "municipal_tax": "Municipal tax", "other_tax": "Other tax",
}


@st.cache_resource
def get_decoder() -> BillDecoder:
    s = load_settings()
    return BillDecoder(LLMClient(s), s.max_image_side, s.fewshot_image)


def pkr(v) -> str:
    return "—" if v is None else f"PKR {v:,.2f}"


def lines_table(lines: list[dict]) -> list[dict]:
    return [{"Type": TYPE_LABELS.get(x["type"], x["type"]), "Amount (PKR)": f"{x['amount']:,.2f}"} for x in lines]


st.title("⚡ Utility Bill Decoder")
st.caption("K-Electric · LESCO · IESCO — upload a bill, see what you owe and why, ask questions.")

try:
    settings = load_settings()
    decoder = get_decoder()
    st.sidebar.success(f"Model: {settings.provider} / {settings.model_name}")
except ConfigError as exc:
    st.error(f"Configuration problem: {exc}")
    st.stop()

tab_one, tab_batch = st.tabs(["Decode a bill", "Batch: generate CSVs"])

# ---------------------------------------------------------------- single bill
with tab_one:
    up = st.file_uploader("Bill image (file name like KESC_0008.png, LESCO_0005.png, IESCO_0004.jpg)",
                          type=["png", "jpg", "jpeg", "webp"])
    if up:
        tmp_dir = Path(tempfile.gettempdir()) / "bill_decoder_ui"
        tmp_dir.mkdir(exist_ok=True)
        path = tmp_dir / up.name
        path.write_bytes(up.getvalue())

        col_img, col_res = st.columns([1, 1.6], gap="large")
        with col_img:
            st.image(up.getvalue(), caption=up.name, width="stretch")

        key = f"res_{up.name}_{len(up.getvalue())}"
        if key not in st.session_state:
            with st.spinner("Reading the bill…"):
                questions = [(f"S{i}", qa["question"]) for i, qa in enumerate(SAMPLE_QA, start=1)]
                st.session_state[key] = decoder.process(path, questions)
        res = st.session_state[key]
        l1 = res.l1

        with col_res:
            st.subheader(f"{l1.get('provider') or ''} bill · {l1.get('bill_month') or 'month unknown'}")
            cards = [
                ("Payable by due date", pkr(l1.get("payable_within_due_date"))),
                ("Due date", l1.get("due_date") or "—"),
                ("Units used", "—" if l1.get("units_consumed") is None else f"{l1['units_consumed']:,}"),
                ("This month's bill", pkr(l1.get("current_bill"))),
                ("Arrears", pkr(l1.get("arrears"))),
                ("If paid late (max)", pkr(l1.get("payable_after_due_date"))),
            ]
            st.markdown(
                '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;'
                'margin:4px 0 14px">'
                + "".join(
                    f'<div style="border:1px solid rgba(128,128,128,.3);border-radius:10px;padding:10px 12px">'
                    f'<div style="font-size:.78rem;opacity:.7">{label}</div>'
                    f'<div style="font-size:1.15rem;font-weight:600;word-break:break-word">{value}</div></div>'
                    for label, value in cards
                )
                + "</div>",
                unsafe_allow_html=True,
            )

            if res.issues:
                st.warning("Consistency checks flagged:\n\n- " + "\n- ".join(res.issues))
            elif not res.errors:
                st.success("All consistency checks passed (sums, readings, payable amounts).")
            for e in res.errors:
                st.error(e)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Charges** — total {pkr(l1.get('total_charges'))}")
                st.dataframe(lines_table(l1.get("charges") or []), hide_index=True, width="stretch")
            with c2:
                st.markdown(f"**Taxes** — total {pkr(l1.get('total_taxes'))}")
                if l1.get("taxes"):
                    st.dataframe(lines_table(l1["taxes"]), hide_index=True, width="stretch")
                else:
                    st.caption("Only a combined tax figure is printed on this bill.")

            with st.expander("Level 1 JSON (exact submission format)"):
                st.json(l1)
                st.code(l1_to_cell(l1), language="json")
            with st.expander("Supporting facts & computed numbers"):
                st.json({"facts": res.facts, "stats": res.stats})

        st.divider()
        st.subheader("Ask about this bill")
        for qid, ans in res.answers.items():
            q = next((qa["question"] for i, qa in enumerate(SAMPLE_QA, 1) if f"S{i}" == qid), qid)
            with st.chat_message("user"):
                st.write(q)
            with st.chat_message("assistant"):
                st.write(ans)

        hist_key = f"{key}_qa"
        st.session_state.setdefault(hist_key, [])
        for q, a in st.session_state[hist_key]:
            with st.chat_message("user"):
                st.write(q)
            with st.chat_message("assistant"):
                st.write(a)

        question = st.chat_input("e.g. Why is my bill higher than last month?")
        if question:
            with st.spinner("Thinking…"):
                image = load_image_bytes(path, settings.max_image_side)
                if not res.stats:
                    res.stats = compute_stats(res.l1, res.facts)
                answer = decoder.answer(image, res, [("Q1", question)])["Q1"]
            st.session_state[hist_key].append((question, answer))
            st.rerun()

# ---------------------------------------------------------------- batch
with tab_batch:
    st.markdown("Runs the same command as `python -m decoder run` and fills the official CSV templates.")
    bills_dir = st.text_input("Bills folder", "../test/bills")
    csv_dir = st.text_input("Templates folder (level1.csv, level2.csv)", "../test/csv")
    out_dir = st.text_input("Output folder", "../output")
    if st.button("Generate level1.csv and level2.csv", type="primary"):
        with st.spinner("Processing all bills… (about 30-40 s per bill on the free tier)"):
            code = cli_main(["run", "--bills", bills_dir, "--csv", csv_dir, "--out", out_dir])
            check = cli_main(["validate", "--csv", csv_dir, "--out", out_dir])
        if code == 0 and check == 0:
            st.success("Done — both CSV files generated and validated.")
        else:
            st.error("Finished with problems — see the terminal output.")
        for name in ("level1.csv", "level2.csv"):
            p = Path(out_dir) / name
            if p.exists():
                st.download_button(f"Download {name}", p.read_bytes(), file_name=name, mime="text/csv")
                with st.expander(f"Preview {name}"):
                    st.text(p.read_text(encoding="utf-8")[:4000])
