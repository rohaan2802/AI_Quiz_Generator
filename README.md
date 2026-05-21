# RACE Quiz Generator — Streamlit UI

The user-interface layer for the **Intelligent Reading Comprehension and Quiz Generation System**. This app wires up Model A (Q&A Generator/Verifier) and Model B (Distractor & Hint Generator) into a polished four-screen Streamlit application.

---

## 🚀 Quick Start

```bash
# 1. install dependencies
pip install -r requirements.txt

# 2. run the app
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## 📁 Project Structure

```
race_ui/
├── app.py                      # main entry point + sidebar nav
├── styles.py                   # global CSS + neon quiz theme
├── inference.py                # Model A & B wrappers (with stub fallbacks)
├── evaluate.py                 # BLEU / ROUGE / METEOR
├── requirements.txt
├── README.md
├── screens/
│   ├── __init__.py
│   ├── article_input.py        # Screen 1
│   ├── quiz_view.py            # Screen 2 (neon theme)
│   ├── hint_panel.py           # Screen 3
│   └── dashboard.py            # Screen 4
├── data/
│   └── raw/
│       ├── train.csv           # RACE training set  ← place here
│       ├── test.csv
│       └── val.csv
└── models/
    ├── model_a/traditional/
    │   ├── answer_verifier.pkl
    │   └── vectorizer.pkl
    └── model_b/traditional/
        ├── distractor_ranker.pkl
        └── hint_scorer.pkl
```

---

## 🧩 Plugging In Your Trained Models

The UI runs immediately with **stub inference functions** (so you can develop the frontend in parallel with the model team). To swap in real models, edit `inference.py` and replace the bodies of these four functions — keeping their signatures unchanged:

| Function | Replaces |
|---|---|
| `generate_question_and_answer(article)` | Model A generation sub-task |
| `verify_answer(article, q, selected, correct)` | Model A verification sub-task |
| `generate_distractors(article, q, correct, n=3)` | Model B distractor ranker |
| `generate_hints(article, q, correct)` | Model B hint scorer |

Pickled scikit-learn models are auto-loaded from `models/` if present.

---

## 📊 Evaluation Metrics

Per the updated project guidance, this UI uses **BLEU, ROUGE-1/2/L, and METEOR** (not Accuracy/Precision) since the task is text generation. Metrics are computed per inference and accumulated on the **Analytics Dashboard** (Screen 4).

NLTK resources (`punkt`, `wordnet`, `omw-1.4`) auto-download on first run.

---

## 🖥️ Screens

| # | Screen | Purpose |
|---|---|---|
| 1 | **Article Input** | Paste a passage *or* load a random RACE sample → submit |
| 2 | **Quiz View** | Neon-styled question pill + 2×2 option grid, Check button |
| 3 | **Hint Panel** | 3 graduated hints; *Reveal Answer* unlocks after all 3 |
| 4 | **Dashboard** | BLEU/ROUGE/METEOR, latency chart, session log + CSV export |

---

## ♿ Accessibility

- High contrast on the neon quiz screen (white text on near-black, with WCAG-AA-friendly purple accents)
- Keyboard navigable (focus rings on all interactive elements)
- Friendly error messages on every failure path
- Loading spinners during inference
- Readable font sizes (16px base)
