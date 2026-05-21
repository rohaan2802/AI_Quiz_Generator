"""
Screen 1 — Article Input
  - Paste a passage OR load a random sample from RACE
  - Submit triggers Model A + Model B inference
"""
from pathlib import Path
import random
import pandas as pd
import streamlit as st
import inference


# Path to RACE dataset (optional — works without it)
RACE_TRAIN_CSV = Path(__file__).parent.parent / "data" / "raw" / "train.csv"


@st.cache_data(show_spinner=False)
def load_race_sample_pool(path: Path = RACE_TRAIN_CSV, n: int = 200) -> pd.DataFrame | None:
    """
    Load a random subset of the RACE training set for the 'Load Sample' button.
    Returns None if the file isn't present (gracefully handled by the UI).
    """
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        # Sample once, cache the subset to keep things snappy
        if len(df) > n:
            df = df.sample(n=n, random_state=42).reset_index(drop=True)
        return df
    except Exception as e:
        print(f"[RACE loader] Failed: {e}")
        return None


def render():
    st.title("📄 Article Input")
    st.caption(
        "Paste a passage or load a random sample from the RACE dataset to "
        "generate a comprehension quiz."
    )

    tab1, tab2 = st.tabs(["✍️  Paste Article", "🎲  Load from RACE Dataset"])

    # ---------- Tab 1: Paste ----------
    with tab1:
        article_input = st.text_area(
            label="Reading passage",
            value=st.session_state.current_article if st.session_state.current_article_id is None else "",
            height=320,
            placeholder="Paste a reading passage here (at least a few sentences)...",
            help="The passage should contain enough information to generate a comprehension question.",
            key="paste_textarea",
        )
        char_count = len(article_input)
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.caption(f"📝 {char_count} characters · {len(article_input.split())} words")
        with col_b:
            if char_count > 0 and char_count < 100:
                st.caption("⚠️ Add more text for better results")

        # Save the typed article into state on every render
        if article_input != st.session_state.current_article and st.session_state.current_article_id is None:
            st.session_state.current_article = article_input

    # ---------- Tab 2: RACE Sample ----------
    with tab2:
        race_df = load_race_sample_pool()
        if race_df is None:
            st.info(
                "📂 RACE dataset not found at `data/raw/train.csv`.\n\n"
                "Download the dataset and place it in `data/raw/` to enable random sampling. "
                "Meanwhile, you can paste any passage in the other tab."
            )
        else:
            st.success(f"✅ RACE dataset loaded — {len(race_df)} samples available")

            col_load, col_show = st.columns([1, 3])
            with col_load:
                if st.button("🎲 Load Random Sample", use_container_width=True, type="primary"):
                    row = race_df.sample(1).iloc[0]
                    st.session_state.current_article = str(row["article"])
                    st.session_state.current_article_id = str(row.get("id", "race_sample"))
                    st.rerun()

            if st.session_state.current_article_id is not None:
                with col_show:
                    st.caption(f"📌 Loaded passage ID: **{st.session_state.current_article_id}**")
                st.text_area(
                    label="Loaded passage (read-only)",
                    value=st.session_state.current_article,
                    height=260,
                    disabled=True,
                    key="race_preview",
                )
                if st.button("✖ Clear loaded sample"):
                    st.session_state.current_article = ""
                    st.session_state.current_article_id = None
                    st.rerun()

    st.divider()

    # ---------- Submit Button ----------
    article = st.session_state.current_article.strip()
    submit_disabled = len(article) < 30

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        submit_clicked = st.button(
            "🚀  Generate Quiz  →",
            use_container_width=True,
            type="primary",
            disabled=submit_disabled,
            help="Paste at least ~30 characters first" if submit_disabled else "Run Model A and Model B",
        )

    if submit_disabled and len(article) > 0:
        st.warning(f"Article is too short ({len(article)} chars). Please add more text — at least 30 characters.")
    elif submit_disabled:
        st.info("👆 Paste an article above or load a random RACE sample to begin.")

    # ---------- Run Inference ----------
    if submit_clicked and not submit_disabled:
        try:
            with st.spinner("🧠 Running Model A and Model B... this takes a few seconds"):
                result = inference.run_full_inference(article)

            # Store everything in session state
            st.session_state.current_question = result["question"]
            st.session_state.options = result["options"]
            st.session_state.correct_answer = result["correct_label"]
            st.session_state.correct_answer_text = result["correct_answer_text"]
            st.session_state.hints = result["hints"]
            st.session_state.hints_revealed = 0
            st.session_state.user_answer = None
            st.session_state.answer_checked = False
            st.session_state.answer_revealed = False
            st.session_state.inference_times.append(result["total_latency"])

            # Navigate to quiz
            st.session_state.screen = "quiz_view"
            st.success("✅ Quiz generated!  Redirecting...")
            st.rerun()

        except Exception as e:
            st.error(
                f"😕 Something went wrong while generating the quiz.\n\n"
                f"**Details:** `{type(e).__name__}: {e}`\n\n"
                "Please try a different passage or check that model files are in place."
            )
