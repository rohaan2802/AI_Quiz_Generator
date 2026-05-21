"""
Intelligent Reading Comprehension & Quiz Generation System
Main Streamlit application entry point.
"""
import streamlit as st
from screens import article_input, quiz_view, hint_panel, dashboard
from styles import GLOBAL_CSS


# ---------- Page Config ----------
st.set_page_config(
    page_title="RACE Quiz Generator",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject global CSS (fonts, contrast, accessibility)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ---------- Session State Initialization ----------
def init_session_state():
    defaults = {
        "screen": "article_input",        # current screen
        "current_article": "",             # the passage
        "current_article_id": None,        # RACE id if loaded from dataset
        "current_question": None,          # generated question text
        "options": None,                   # dict {"A": ..., "B": ..., "C": ..., "D": ...}
        "correct_answer": None,            # "A" / "B" / "C" / "D"
        "user_answer": None,               # user's selected option
        "answer_checked": False,           # whether Check was clicked
        "hints": [],                       # list of 3 hint strings from Model B
        "hints_revealed": 0,               # how many hints user has revealed (0-3)
        "answer_revealed": False,          # whether final answer was revealed
        "session_log": [],                 # list of dicts for dashboard table
        "inference_times": [],             # list of latency floats (seconds)
        "metric_history": [],              # list of dicts: {bleu, rouge_l, meteor}
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ---------- Sidebar Navigation ----------
SCREENS = {
    "article_input": "📄  Article Input",
    "quiz_view":     "❓  Quiz",
    "hint_panel":    "💡  Hints",
    "dashboard":     "📊  Analytics Dashboard",
}

with st.sidebar:
    st.markdown("### 🧠 RACE Quiz Generator")
    st.caption("AI-powered Reading Comprehension")
    st.divider()

    for key, label in SCREENS.items():
        is_active = st.session_state.screen == key
        if st.button(
            label,
            key=f"nav_{key}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.screen = key
            st.rerun()

    st.divider()

    # Quick session info
    st.caption("**Session Stats**")
    st.caption(f"Quizzes attempted: **{len(st.session_state.session_log)}**")
    if st.session_state.inference_times:
        avg_ms = sum(st.session_state.inference_times) / len(st.session_state.inference_times) * 1000
        st.caption(f"Avg latency: **{avg_ms:.0f} ms**")

    st.divider()
    if st.button("🔄  Reset Session", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ---------- Screen Router ----------
screen = st.session_state.screen

if screen == "article_input":
    article_input.render()
elif screen == "quiz_view":
    quiz_view.render()
elif screen == "hint_panel":
    hint_panel.render()
elif screen == "dashboard":
    dashboard.render()
else:
    st.error("Unknown screen. Resetting...")
    st.session_state.screen = "article_input"
    st.rerun()
