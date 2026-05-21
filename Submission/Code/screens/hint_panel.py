"""
Screen 3 — Hint Panel
  - 3 graduated hints revealed one by one
  - 'Reveal Answer' appears only after all 3 hints have been shown
"""
import streamlit as st


def _navigate(screen: str):
    st.session_state.screen = screen
    st.rerun()


def render():
    st.title("💡 Hints")
    st.caption("Use these graduated clues to work your way to the answer.")

    # ---- Guard ----
    if not st.session_state.current_question or not st.session_state.hints:
        st.warning("📭 No hints available. Generate a quiz from **Article Input** first.")
        if st.button("← Go to Article Input", type="primary"):
            _navigate("article_input")
        return

    # ---- Top actions ----
    c1, c2, _ = st.columns([1, 1, 3])
    with c1:
        if st.button("← Back to Quiz", use_container_width=True):
            _navigate("quiz_view")
    with c2:
        if st.button("🔄 Reset Hints", use_container_width=True):
            st.session_state.hints_revealed = 0
            st.session_state.answer_revealed = False
            st.rerun()

    # ---- Article expander ----
    with st.expander("📖  Re-read the passage"):
        st.write(st.session_state.current_article)

    # ---- Question reminder ----
    st.subheader("Question")
    st.info(st.session_state.current_question)

    st.divider()

    # ---- Hint reveal logic ----
    revealed = st.session_state.hints_revealed
    hints = st.session_state.hints

    # Hint labels for visual hierarchy
    hint_meta = [
        {"emoji": "🔍", "label": "Hint 1 — General Clue", "color": "blue"},
        {"emoji": "🎯", "label": "Hint 2 — More Specific", "color": "violet"},
        {"emoji": "💎", "label": "Hint 3 — Almost There", "color": "orange"},
    ]

    for i in range(3):
        if i < revealed:
            # Already revealed → show it
            meta = hint_meta[i]
            with st.container(border=True):
                st.markdown(f"### {meta['emoji']} {meta['label']}")
                st.markdown(f"<p style='font-size:1.05rem; line-height:1.6;'>{hints[i]}</p>",
                            unsafe_allow_html=True)
        elif i == revealed:
            # Next available → show button
            meta = hint_meta[i]
            if st.button(
                f"👁  Show {meta['label']}",
                key=f"reveal_hint_{i}",
                use_container_width=True,
            ):
                st.session_state.hints_revealed += 1
                st.rerun()
            break  # don't show further locked hints

    # ---- Locked hints preview ----
    if revealed < 3:
        for i in range(revealed + 1, 3):
            meta = hint_meta[i]
            st.caption(f"🔒 {meta['label']} — locked (reveal previous hints first)")

    # ---- Reveal Answer (only after all 3 hints) ----
    st.divider()
    if revealed >= 3:
        if not st.session_state.answer_revealed:
            cc1, cc2, cc3 = st.columns([1, 2, 1])
            with cc2:
                if st.button(
                    "🎁  Reveal the Answer",
                    use_container_width=True,
                    type="primary",
                ):
                    st.session_state.answer_revealed = True
                    st.rerun()
        else:
            with st.container(border=True):
                st.markdown(f"### ✅ The Correct Answer")
                st.success(
                    f"**Option {st.session_state.correct_answer}:**  "
                    f"{st.session_state.correct_answer_text}"
                )
                if st.button("🔁  Try Another Article", type="primary", use_container_width=True):
                    # Clear and go back
                    st.session_state.hints_revealed = 0
                    st.session_state.answer_revealed = False
                    _navigate("article_input")
    else:
        st.caption(f"💭  Reveal all 3 hints to unlock the answer ({revealed}/3 used)")
