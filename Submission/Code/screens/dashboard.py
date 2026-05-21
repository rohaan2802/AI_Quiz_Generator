"""
Screen 4 — Developer / Analytics Dashboard
  - Generation metrics (BLEU, ROUGE-1/2/L, METEOR) — replaces classification metrics
  - Inference latency tracking
  - Session log table + CSV export
"""
import io
import pandas as pd
import streamlit as st


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def render():
    st.title("📊 Analytics Dashboard")
    st.caption(
        "Generation-quality metrics (BLEU / ROUGE / METEOR) and latency tracking "
        "for the current session."
    )

    # ---- Empty state ----
    if not st.session_state.session_log:
        st.info(
            "📭 No inferences logged yet.\n\n"
            "Generate a quiz on **Article Input** and check at least one answer "
            "to populate the dashboard."
        )
        if st.button("→ Go to Article Input", type="primary"):
            st.session_state.screen = "article_input"
            st.rerun()
        return

    # =====================================================================
    # SECTION 1: NLP Generation Metrics
    # =====================================================================
    st.subheader("📝 Generation-Quality Metrics")
    st.caption(
        "Project requirement: BLEU, ROUGE, and METEOR are used (not Accuracy/Precision) "
        "since this is a text-generation task. Reference: RACE gold answer · "
        "Hypothesis: model output."
    )

    metrics = st.session_state.metric_history
    if metrics:
        avg_bleu   = _avg([m["bleu"]   for m in metrics])
        avg_r1     = _avg([m["rouge1"] for m in metrics])
        avg_r2     = _avg([m["rouge2"] for m in metrics])
        avg_rl     = _avg([m["rougeL"] for m in metrics])
        avg_meteor = _avg([m["meteor"] for m in metrics])
    else:
        avg_bleu = avg_r1 = avg_r2 = avg_rl = avg_meteor = 0.0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("BLEU", f"{avg_bleu:.3f}", help="n-gram overlap (BLEU-4 with smoothing)")
    col2.metric("ROUGE-1", f"{avg_r1:.3f}", help="Unigram overlap F1")
    col3.metric("ROUGE-2", f"{avg_r2:.3f}", help="Bigram overlap F1")
    col4.metric("ROUGE-L", f"{avg_rl:.3f}", help="Longest common subsequence F1")
    col5.metric("METEOR", f"{avg_meteor:.3f}", help="Synonym + stem aware alignment")

    # ---- Trend chart ----
    if len(metrics) >= 2:
        st.markdown("##### Metric Trend Across Inferences")
        trend_df = pd.DataFrame(metrics)
        trend_df.index = range(1, len(trend_df) + 1)
        trend_df.index.name = "Inference #"
        st.line_chart(trend_df[["bleu", "rougeL", "meteor"]])
    else:
        st.caption("📈 Run more quizzes to see metric trends over time.")

    st.divider()

    # =====================================================================
    # SECTION 2: Latency
    # =====================================================================
    st.subheader("⚡ Inference Latency")
    times_ms = [t * 1000 for t in st.session_state.inference_times]

    if times_ms:
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Avg latency", f"{_avg(times_ms):.0f} ms")
        col_b.metric("Min latency", f"{min(times_ms):.0f} ms")
        col_c.metric("Max latency", f"{max(times_ms):.0f} ms")

        if len(times_ms) >= 2:
            lat_df = pd.DataFrame({"Latency (ms)": times_ms})
            lat_df.index = range(1, len(lat_df) + 1)
            lat_df.index.name = "Request #"
            st.line_chart(lat_df)

        # 10-second SLA check (from project doc)
        slow = [t for t in times_ms if t > 10_000]
        if slow:
            st.warning(f"⚠️  {len(slow)} request(s) exceeded the 10-second target.")
        else:
            st.success("✅ All requests completed within the 10-second target.")
    else:
        st.caption("No latency data yet.")

    st.divider()

    # =====================================================================
    # SECTION 3: Session Log
    # =====================================================================
    st.subheader("📋 Session Log")

    log_df = pd.DataFrame(st.session_state.session_log)

    # Attach generation metrics if available (align by index)
    if metrics and len(metrics) == len(log_df):
        for k in ["bleu", "rougeL", "meteor"]:
            log_df[k] = [round(m[k], 3) for m in metrics]

    # Trim long question text for the table
    if "question" in log_df.columns:
        log_df["question"] = log_df["question"].astype(str).str.slice(0, 60) + "…"

    # Reorder columns for readability
    preferred = ["article_id", "question", "user_answer", "correct_answer",
                 "is_correct", "confidence", "bleu", "rougeL", "meteor", "latency_ms"]
    cols = [c for c in preferred if c in log_df.columns]
    log_df = log_df[cols]

    st.dataframe(log_df, use_container_width=True, hide_index=True)
    st.caption(f"Total entries: **{len(log_df)}**")

    # ---- CSV Export ----
    csv_buf = io.StringIO()
    log_df.to_csv(csv_buf, index=False)
    col_dl, col_clear = st.columns(2)
    with col_dl:
        st.download_button(
            "⬇️  Download session log (CSV)",
            data=csv_buf.getvalue(),
            file_name="race_session_log.csv",
            mime="text/csv",
            use_container_width=True,
            type="primary",
        )
    with col_clear:
        if st.button("🗑  Clear log", use_container_width=True):
            st.session_state.session_log = []
            st.session_state.inference_times = []
            st.session_state.metric_history = []
            st.rerun()
