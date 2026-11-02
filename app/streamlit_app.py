"""Thin Streamlit UI over the demo pipeline: run_demo plus charts. All data shaping lives in maid.gui_data."""
import json

import altair as alt
import pandas as pd
import streamlit as st

from maid.demo import run_demo
from maid.graph import DEFAULT_SETTINGS
from maid.gui_data import (
    acceptability_rows,
    interval_rows,
    matrix_rows,
    pipeline_dot,
    ranking_rows,
    score_rows,
    weight_rows,
)

st.set_page_config(page_title="MAID demo", layout="wide")


@st.cache_data(show_spinner="Running the pipeline...")
def run(settings_json: str, overrides_json: str) -> dict:
    """Run the demo pipeline; Pydantic objects in the state become plain dicts."""
    state = run_demo(json.loads(settings_json), json.loads(overrides_json))
    state["qualitative"] = [s.model_dump() for s in state["qualitative"]]
    state["overrides"] = [o.model_dump() for o in state["overrides"]]
    return state


class _Row:
    """Attribute access over a dict so gui_data helpers work on the cached, dict-ified state."""
    def __init__(self, d):
        self.__dict__.update(d)


def as_state(state: dict) -> dict:
    """Cached state with qualitative/overrides turned back into attribute-style rows for gui_data."""
    return {**state, "qualitative": [_Row(d) for d in state["qualitative"]],
            "overrides": [_Row(d) for d in state["overrides"]]}


st.title("MAID: multi-agent investment decision-making")
overrides = st.session_state.setdefault("overrides", [])

with st.sidebar:
    st.warning("Synthetic demo data: invented companies, not real ones.")
    weighting = st.selectbox("Weighting", ["entropy", "critic", "equal"], index=["entropy", "critic", "equal"].index(DEFAULT_SETTINGS["weighting"]))
    k = st.slider("K samples per score", 1, 15, DEFAULT_SETTINGS["k"])
    seed = st.number_input("Seed", 0, 10_000, DEFAULT_SETTINGS["seed"], step=1)
    n_draws = st.slider("Robustness draws", 100, 2000, DEFAULT_SETTINGS["n_draws"], step=100)
    conc = st.select_slider("Dirichlet concentration", [10, 30, 100, 300, 1000], value=int(DEFAULT_SETTINGS["concentration"]))

settings = {"weighting": weighting, "k": k, "seed": int(seed), "n_draws": n_draws, "concentration": float(conc)}
try:
    state = as_state(run(json.dumps(settings), json.dumps(overrides)))
except Exception as e:  # invalid overrides surface from the pipeline's validation
    st.error(f"Pipeline error: {e}")
    st.stop()

tabs = st.tabs(["Pipeline", "Inputs", "Scores & review", "Weights", "Ranking", "Robustness", "Report"])

with tabs[0]:
    st.graphviz_chart(pipeline_dot())
    st.markdown(
        "- **ingest**: loads the synthetic companies, numbers and filing excerpts.\n"
        "- **score_qualitative**: a stub scorer draws K scored samples per criterion with a quoted evidence sentence.\n"
        "- **human_review**: you may override any score, with a reason; the pipeline resumes with your changes.\n"
        "- **mcdm / robustness**: weights, TOPSIS and SAW ranks, then rank intervals from resampling."
    )
    st.caption("Legend: green = real, amber = demo (synthetic), grey = stub.")
    st.info("LLMs never rank: they only score with cited evidence. A deterministic MCDM engine computes weights and ranks.")

with tabs[1]:
    st.subheader("Decision matrix (after overrides)")
    st.dataframe(pd.DataFrame(matrix_rows(state)), hide_index=True)
    company = st.selectbox("Filing excerpt", state["companies"])
    st.text(state["filings"][company])

with tabs[2]:
    st.subheader("Scores")
    st.dataframe(pd.DataFrame(score_rows(state)), hide_index=True)
    with st.form("override"):
        c1, c2, c3 = st.columns(3)
        o_company = c1.selectbox("Company", state["companies"])
        o_crit = c2.selectbox("Criterion", sorted({s.criterion for s in state["qualitative"]}))
        o_score = c3.slider("New score", 1, 9, 5)
        o_reason = st.text_input("Reason (required)")
        if st.form_submit_button("Add override"):
            overrides.append({"company": o_company, "criterion": o_crit, "score": o_score, "reason": o_reason})
            st.rerun()
    st.subheader("Active overrides")
    if overrides:
        st.dataframe(pd.DataFrame(overrides), hide_index=True)
        if st.button("Clear overrides"):
            overrides.clear()
            st.rerun()
    else:
        st.caption("None.")

with tabs[3]:
    w = pd.DataFrame(weight_rows(state))
    st.altair_chart(alt.Chart(w).mark_bar().encode(
        x=alt.X("method:N", title=None), y=alt.Y("weight:Q"), color="method:N",
        column=alt.Column("criterion:N"), tooltip=["method", "criterion", "weight", "used"]), width="stretch")
    st.write(f"Weighting in use: **{weighting}**. The methods disagree because they reward different things "
             "(dispersion vs. dispersion and independence), so the weights, and the ranking, depend on the choice. "
             "See `docs/architecture/uncertainty.md`.")

with tabs[4]:
    r = pd.DataFrame(ranking_rows(state))
    st.dataframe(r, hide_index=True)
    st.metric("Kendall tau, TOPSIS vs SAW", f"{state['method_agreement']['kendall_tau_topsis_saw']:.3f}")
    st.altair_chart(alt.Chart(r).mark_circle(size=90).encode(
        x=alt.X("rank:Q", title="TOPSIS rank"), y=alt.Y("saw_rank:Q", title="SAW rank"),
        tooltip=["company", "rank", "saw_rank"]), width="stretch")

with tabs[5]:
    src = st.radio("Perturbation", ["bootstrap", "dirichlet"], horizontal=True)
    iv = pd.DataFrame(interval_rows(state, src))
    order = list(iv["company"])
    base = alt.Chart(iv).encode(y=alt.Y("company:N", sort=order))
    st.altair_chart(base.mark_rule().encode(x=alt.X("lo:Q", title="Rank (1 = best)"), x2="hi:Q")
                    + base.mark_point(filled=True, size=80).encode(x="point:Q", tooltip=["company", "point", "lo", "hi"]),
                    width="stretch")
    st.caption("The bar spans the 5th to 95th percentile of rank over the draws (a 90% interval); "
               "a wide bar means the rank is not trustworthy.")
    acc = pd.DataFrame(acceptability_rows(state, src))
    st.altair_chart(alt.Chart(acc).mark_rect().encode(
        x=alt.X("rank:O", title="Rank"), y=alt.Y("company:N", sort=order),
        color=alt.Color("share:Q", scale=alt.Scale(scheme="blues")), tooltip=["company", "rank", "share"]),
        width="stretch")

with tabs[6]:
    st.markdown(state["report"])
