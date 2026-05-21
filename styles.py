"""
CSS styles for the Streamlit app.
Two themes:
  - GLOBAL_CSS: applied app-wide (fonts, contrast, accessibility)
  - QUIZ_CSS:   applied only on the quiz screen (neon dark theme)
"""

# ---------- Global App Styles ----------
GLOBAL_CSS = """
<style>
    /* Readable, accessible base typography */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 16px;
    }

    /* Larger, more readable headers */
    h1 { font-size: 2.2rem !important; font-weight: 700 !important; }
    h2 { font-size: 1.6rem !important; font-weight: 600 !important; }
    h3 { font-size: 1.3rem !important; font-weight: 600 !important; }

    /* Sidebar nav buttons - left aligned text */
    section[data-testid="stSidebar"] .stButton > button {
        text-align: left;
        justify-content: flex-start;
        font-weight: 500;
    }

    /* Better focus rings for keyboard accessibility */
    button:focus-visible,
    input:focus-visible,
    textarea:focus-visible {
        outline: 3px solid #6366f1 !important;
        outline-offset: 2px !important;
    }

    /* Friendly metric cards */
    [data-testid="stMetric"] {
        background-color: rgba(99, 102, 241, 0.05);
        border: 1px solid rgba(99, 102, 241, 0.2);
        padding: 16px;
        border-radius: 12px;
    }
</style>
"""


# ---------- Neon Quiz Theme (Screen 2) ----------
# Matches the reference screenshot: black background, glowing purple borders,
# pill-shaped question banner with "?" badge, 2x2 grid of A/B/C/D options.
QUIZ_CSS = """
<style>
    /* --- Quiz container (dark canvas) --- */
    .quiz-container {
        background: #0a0a14;
        padding: 48px 32px;
        border-radius: 20px;
        margin: 16px 0;
    }

    /* --- Question pill --- */
    .quiz-question-wrap {
        display: flex;
        justify-content: center;
        position: relative;
        margin-bottom: 56px;
    }
    .quiz-question {
        background: #0a0a14;
        border: 2.5px solid #a855f7;
        border-radius: 999px;
        padding: 28px 56px;
        color: #ffffff;
        font-size: 1.05rem;
        font-weight: 500;
        text-align: center;
        max-width: 720px;
        width: 100%;
        min-height: 80px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow:
            0 0 16px rgba(168, 85, 247, 0.5),
            inset 0 0 8px rgba(168, 85, 247, 0.15);
        position: relative;
    }
    .quiz-question-badge {
        position: absolute;
        bottom: -22px;
        left: 50%;
        transform: translateX(-50%);
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: #0a0a14;
        border: 2.5px solid #a855f7;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        font-size: 1.2rem;
        font-weight: 700;
        box-shadow: 0 0 12px rgba(168, 85, 247, 0.6);
    }

    /* --- Option pills --- */
    /* Style Streamlit buttons inside .quiz-options-zone to look like pills */
    .quiz-options-zone .stButton > button {
        background: #0a0a14 !important;
        color: #ffffff !important;
        border: 2px solid #6366f1 !important;
        border-radius: 999px !important;
        padding: 18px 28px !important;
        font-size: 1rem !important;
        font-weight: 500 !important;
        width: 100% !important;
        min-height: 60px !important;
        text-align: left !important;
        justify-content: flex-start !important;
        box-shadow:
            0 0 10px rgba(99, 102, 241, 0.4),
            inset 0 0 6px rgba(99, 102, 241, 0.1) !important;
        transition: all 0.2s ease !important;
    }
    .quiz-options-zone .stButton > button:hover {
        border-color: #a855f7 !important;
        box-shadow:
            0 0 18px rgba(168, 85, 247, 0.7),
            inset 0 0 10px rgba(168, 85, 247, 0.2) !important;
        transform: translateY(-2px);
    }
    /* Selected option (primary type) */
    .quiz-options-zone .stButton > button[kind="primary"] {
        border-color: #c084fc !important;
        background: rgba(168, 85, 247, 0.15) !important;
        box-shadow:
            0 0 22px rgba(192, 132, 252, 0.85),
            inset 0 0 14px rgba(192, 132, 252, 0.25) !important;
    }

    /* --- Verdict banners (after Check) --- */
    .verdict-correct {
        background: rgba(34, 197, 94, 0.15);
        border: 2px solid #22c55e;
        color: #ffffff;
        padding: 20px 28px;
        border-radius: 16px;
        margin-top: 24px;
        font-size: 1.05rem;
        box-shadow: 0 0 18px rgba(34, 197, 94, 0.45);
    }
    .verdict-wrong {
        background: rgba(239, 68, 68, 0.15);
        border: 2px solid #ef4444;
        color: #ffffff;
        padding: 20px 28px;
        border-radius: 16px;
        margin-top: 24px;
        font-size: 1.05rem;
        box-shadow: 0 0 18px rgba(239, 68, 68, 0.45);
    }

    /* --- Article re-read box on quiz screen --- */
    .quiz-article-box {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(168, 85, 247, 0.3);
        color: #e5e5e5;
        padding: 16px 20px;
        border-radius: 12px;
        font-size: 0.95rem;
        line-height: 1.6;
        max-height: 240px;
        overflow-y: auto;
    }
</style>
"""
