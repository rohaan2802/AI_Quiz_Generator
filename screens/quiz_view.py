"""
Screen 2 — Question & Answer Quiz View
  - Dark neon theme (matches reference screenshot)
  - Pill-shaped question banner with ? badge
  - 2x2 grid of A/B/C/D option pills
  - Check button → green (correct) / red (incorrect) verdict
"""
import time
import streamlit as st
import inference
from styles import QUIZ_CSS


def _navigate(screen: str):
    st.session_state.screen = screen
    st.rerun()


def _select_option(label: str):
    """Toggle/select an option (called by option button clicks)."""
    if not st.session_state.answer_checked:
        st.session_state.user_answer = label


def _check_answer():
    """Run Model A verifier on the user's selected option and log the result."""
    if st.session_state.user_answer is None:
        return

    selected_text = st.session_state.options[st.session_state.user_answer]
    correct_text = st.session_state.correct_answer_text

    start = time.time()
    result = inference.verify_answer(
        article=st.session_state.current_article,
        question=st.session_state.current_question,
        selected_option_text=selected_text,
        correct_option_text=correct_text,
    )
    latency = time.time() - start

    st.session_state.answer_checked = True
    st.session_state.last_verification = result

    # ---- Log this attempt (for the dashboard) ----
    st.session_state.session_log.append({
        "article_id": st.session_state.current_article_id or "pasted",
        "question": st.session_state.current_question,
        "user_answer": st.session_state.user_answer,
        "correct_answer": st.session_state.correct_answer,
        "is_correct": result["is_correct"],
        "confidence": result["confidence"],
        "latency_ms": round(latency * 1000, 1),
    })

    # ---- Compute & log NLP generation metrics for the dashboard ----
    try:
        from evaluate import compute_all
        # Compare generated correct option against the typed/loaded user answer
        # text as a proxy reference (when running on RACE, this could be the
        # original "answer" column for proper reference).
        scores = compute_all(reference=correct_text, hypothesis=selected_text)
        st.session_state.metric_history.append(scores)
    except Exception as e:
        print(f"[evaluate] metric logging failed: {e}")


def render():
    # Inject neon CSS for this screen only
    st.markdown(QUIZ_CSS, unsafe_allow_html=True)

    # ---- Guard: no question loaded ----
    if not st.session_state.current_question or not st.session_state.options:
        st.title("❓ Quiz")
        st.warning("📭 No quiz loaded yet. Head to **Article Input** and submit a passage.")
        if st.button("← Go to Article Input", type="primary"):
            _navigate("article_input")
        return

    # ---- Header ----
    col_title, col_actions = st.columns([3, 2])
    with col_title:
        st.title("❓ Quiz")
    with col_actions:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💡 Hints", use_container_width=True):
                _navigate("hint_panel")
        with c2:
            if st.button("🔄 New Article", use_container_width=True):
                # Clear quiz state so user starts fresh
                for k in ["current_question", "options", "correct_answer",
                          "user_answer", "answer_checked"]:
                    st.session_state[k] = None if k != "answer_checked" else False
                _navigate("article_input")

    # ---- Collapsible re-read of the article ----
    with st.expander("📖  Re-read the passage"):
        st.markdown(
            f'<div class="quiz-article-box">{st.session_state.current_article}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ============== Quiz Visual (Neon Theme) ==============
    st.markdown('<div class="quiz-container">', unsafe_allow_html=True)

    # ---- Question pill with ? badge ----
    st.markdown(
        f"""
        <div class="quiz-question-wrap">
            <div class="quiz-question">
                {st.session_state.current_question}
                <div class="quiz-question-badge">?</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Options grid (A B / C D) ----
    st.markdown('<div class="quiz-options-zone">', unsafe_allow_html=True)

    options = st.session_state.options
    selected = st.session_state.user_answer
    locked = st.session_state.answer_checked  # disable clicks after Check

    row1 = st.columns(2, gap="medium")
    row2 = st.columns(2, gap="medium")
    cells = [(row1[0], "A"), (row1[1], "B"), (row2[0], "C"), (row2[1], "D")]

    for col, label in cells:
        with col:
            text = options.get(label, "")
            display = f"**{label}**   {text}"
            is_selected = (selected == label)
            if st.button(
                display,
                key=f"opt_{label}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
                disabled=locked,
            ):
                _select_option(label)
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)  # close quiz-options-zone

    # ---- Check button ----
    st.markdown("<br>", unsafe_allow_html=True)
    cc1, cc2, cc3 = st.columns([1, 2, 1])
    with cc2:
        if not locked:
            if st.button(
                "✓  Check My Answer",
                use_container_width=True,
                type="primary",
                disabled=(selected is None),
                help="Pick an option above first" if selected is None else "Verify with Model A",
            ):
                _check_answer()
                st.rerun()
        else:
            if st.button("🔁  Try Another Question", use_container_width=True, type="primary"):
                # Reset answer state, go back to article input for fresh inference
                st.session_state.user_answer = None
                st.session_state.answer_checked = False
                _navigate("article_input")

    # ---- Verdict banner ----
    if locked:
        result = st.session_state.get("last_verification", {})
        is_correct = result.get("is_correct", False)
        confidence = result.get("confidence", 0.0)
        correct_label = st.session_state.correct_answer
        correct_text = st.session_state.correct_answer_text

        if is_correct:
            st.markdown(
                f"""
                <div class="verdict-correct">
                    <strong>✅ Correct!</strong>  Model A verified your answer
                    (confidence: {confidence:.0%}).
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="verdict-wrong">
                    <strong>❌ Incorrect.</strong>  The correct answer was <strong>{correct_label}</strong>:
                    <em>{correct_text}</em>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)  # close quiz-container
