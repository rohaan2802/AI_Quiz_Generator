"""
Inference wrappers for Model A (Q&A Generator/Verifier) and Model B
(Distractor/Hint Generator).

This file connects the Streamlit UI to the trained traditional ML models.

Expected folder structure:

race_ui/
├── inference.py
├── data/
│   ├── raw/
│   │   └── test.csv
│   └── processed/
│       ├── model_a_test_full.csv
│       └── model_b_test_full.csv
└── models/
    ├── model_a/
    │   └── traditional/
    │       ├── answer_verifier.pkl
    │       ├── vectorizer.pkl
    │       ├── numeric_scaler.pkl
    │       ├── qgen_vectorizer.pkl
    │       └── qgen_ranker.pkl
    └── model_b/
        └── traditional/
            ├── vectorizer.pkl
            ├── distractor_ranker.pkl
            └── hint_scorer.pkl
"""

from __future__ import annotations

import ast
import math
import os
import random
import re
import string
import time
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import streamlit as st
from scipy.sparse import hstack
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


# ============================================================
# Paths
# ============================================================

ROOT = Path(__file__).parent

MODEL_A_DIR = ROOT / "models" / "model_a" / "traditional"
MODEL_B_DIR = ROOT / "models" / "model_b" / "traditional"

DATA_RAW_DIR = ROOT / "data" / "raw"
DATA_PROCESSED_DIR = ROOT / "data" / "processed"

RAW_TEST_PATH = DATA_RAW_DIR / "test.csv"
PROCESSED_MODEL_B_TEST_PATH = DATA_PROCESSED_DIR / "model_b_test_full.csv"


# ============================================================
# Global settings
# ============================================================

STOPWORDS = set(ENGLISH_STOP_WORDS)

MODEL_B_FEATURE_COLS = [
    "cos_candidate_answer",
    "cos_candidate_question",
    "cos_candidate_article",
    "candidate_word_len",
    "answer_word_len",
    "length_diff",
    "char_overlap_answer",
    "word_overlap_answer",
    "word_overlap_question",
    "candidate_frequency_article",
    "candidate_in_question",
    "candidate_same_as_answer",
    "candidate_contains_answer",
    "answer_contains_candidate",
]

HINT_FEATURE_COLS = [
    "cos_question_sentence",
    "cos_answer_sentence",
    "cos_question_answer_sentence",
    "question_sentence_overlap",
    "answer_sentence_overlap",
    "sentence_position_norm",
    "sentence_word_len",
    "contains_correct_answer",
]

MODEL_A_NUMERIC_FEATURE_COLS = [
    "cos_article_option",
    "cos_question_option",
    "cos_article_question",
    "article_len",
    "question_len",
    "option_len",
    "question_option_overlap",
    "article_option_overlap",
    "article_question_overlap",
    "question_option_overlap_ratio",
    "article_option_overlap_ratio",
]

QGEN_FEATURE_COLS = [
    "sentence_score",
    "contains_answer",
    "sentence_position",
    "generated_q_len",
    "source_sentence_len",
    "correct_answer_len",
    "q_sent_overlap",
    "q_ans_overlap",
    "q_sent_overlap_ratio",
    "q_ans_overlap_ratio",
    "cos_q_sent",
    "cos_q_ans",
    "cos_q_ctx",
    "wh_who",
    "wh_what",
    "wh_where",
    "wh_when",
    "wh_why",
    "wh_how",
    "wh_which",
    "answer_type_who",
    "answer_type_what",
    "answer_type_where",
    "answer_type_when",
    "template_is_cloze",
    "template_is_according",
    "template_is_generic",
]


# ============================================================
# Generic text helpers
# ============================================================

def safe_text(x: Any) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x)


def normalize_text(text: str) -> str:
    text = safe_text(text).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def remove_punctuation(text: str) -> str:
    return safe_text(text).translate(str.maketrans("", "", string.punctuation))


def tokenize_words(text: str) -> list[str]:
    text = normalize_text(remove_punctuation(text))
    return re.findall(r"\b[a-zA-Z][a-zA-Z0-9]*\b", text)


def content_words(text: str) -> list[str]:
    return [
        token
        for token in tokenize_words(text)
        if token not in STOPWORDS and len(token) > 2
    ]


def word_overlap(a: str, b: str) -> float:
    a_words = set(content_words(a))
    b_words = set(content_words(b))

    if not a_words or not b_words:
        return 0.0

    return len(a_words & b_words) / len(a_words | b_words)


def char_overlap(a: str, b: str) -> float:
    a_chars = set(normalize_text(remove_punctuation(a)).replace(" ", ""))
    b_chars = set(normalize_text(remove_punctuation(b)).replace(" ", ""))

    if not a_chars or not b_chars:
        return 0.0

    return len(a_chars & b_chars) / len(a_chars | b_chars)


def candidate_frequency_in_article(candidate: str, article: str) -> int:
    candidate_norm = normalize_text(candidate)
    article_norm = normalize_text(article)

    if not candidate_norm:
        return 0

    return article_norm.count(candidate_norm)


def split_sentences(text: str) -> list[str]:
    text = safe_text(text).strip()

    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

    return sentences


def parse_sentence_list(x: Any) -> list[str]:
    if isinstance(x, list):
        return [safe_text(s) for s in x if safe_text(s).strip()]

    x = safe_text(x)

    try:
        parsed = ast.literal_eval(x)
        if isinstance(parsed, list):
            return [safe_text(s) for s in parsed if safe_text(s).strip()]
    except Exception:
        pass

    return split_sentences(x)


def sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-float(x)))
    except Exception:
        return 0.5


# ============================================================
# Data loading
# ============================================================

@st.cache_data(show_spinner=False)
def load_sample_data() -> pd.DataFrame | None:
    """
    Loads the UI sample dataset.

    Priority:
    1. data/raw/test.csv
    2. data/processed/model_b_test_full.csv

    model_b_test_full.csv is preferred for the UI because it is question-level
    and contains article, question, correct_answer, distractors, and article_sentences.
    """
    path = None

    if RAW_TEST_PATH.exists():
        path = RAW_TEST_PATH
    elif PROCESSED_MODEL_B_TEST_PATH.exists():
        path = PROCESSED_MODEL_B_TEST_PATH

    if path is None:
        return None

    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        print(f"[Data] Failed to load sample data: {e}")
        return None


def lookup_sample_by_article(article: str) -> dict | None:
    """
    If the article came from data/raw/test.csv, recover the original RACE
    question and correct_answer. This makes the Streamlit demo much stronger
    than trying to generate a question from article text alone.
    """
    df = load_sample_data()

    if df is None or "article" not in df.columns:
        return None

    article_norm = normalize_text(article)

    if not article_norm:
        return None

    # Exact normalized match first.
    try:
        matches = df[df["article"].astype(str).map(normalize_text) == article_norm]
        if len(matches) > 0:
            row = matches.iloc[0]
            return row.to_dict()
    except Exception:
        pass

    # Fallback: prefix match for cases where the UI trims text.
    try:
        short = article_norm[:300]
        matches = df[df["article"].astype(str).map(lambda x: normalize_text(x).startswith(short))]
        if len(matches) > 0:
            row = matches.iloc[0]
            return row.to_dict()
    except Exception:
        pass

    return None


# ============================================================
# Model loading
# ============================================================

@st.cache_resource(show_spinner=False)
def load_model_a() -> dict | None:
    """
    Loads Model A artifacts.

    Required for answer verification:
    - answer_verifier.pkl
    - vectorizer.pkl
    - numeric_scaler.pkl

    Optional for question generation:
    - qgen_vectorizer.pkl
    - qgen_ranker.pkl
    """
    paths = {
        "verifier": MODEL_A_DIR / "answer_verifier.pkl",
        "vectorizer": MODEL_A_DIR / "vectorizer.pkl",
        "numeric_scaler": MODEL_A_DIR / "numeric_scaler.pkl",
        "qgen_vectorizer": MODEL_A_DIR / "qgen_vectorizer.pkl",
        "qgen_ranker": MODEL_A_DIR / "qgen_ranker.pkl",
    }

    out = {}

    for key, path in paths.items():
        if path.exists():
            try:
                out[key] = joblib.load(path)
                print(f"[Model A] Loaded {key}: {path}")
            except Exception as e:
                print(f"[Model A] Failed to load {key}: {e}")

    return out if out else None


@st.cache_resource(show_spinner=False)
def load_model_b() -> dict | None:
    """
    Loads Model B artifacts.

    Required:
    - vectorizer.pkl
    - distractor_ranker.pkl
    - hint_scorer.pkl
    """
    paths = {
        "vectorizer": MODEL_B_DIR / "vectorizer.pkl",
        "distractor_ranker": MODEL_B_DIR / "distractor_ranker.pkl",
        "hint_scorer": MODEL_B_DIR / "hint_scorer.pkl",
    }

    out = {}

    for key, path in paths.items():
        if path.exists():
            try:
                out[key] = joblib.load(path)
                print(f"[Model B] Loaded {key}: {path}")
            except Exception as e:
                print(f"[Model B] Failed to load {key}: {e}")

    return out if out else None


# ============================================================
# Sparse cosine helpers
# ============================================================

def paired_cosine_sparse(A, B) -> np.ndarray:
    numer = A.multiply(B).sum(axis=1).A1
    A_norm = np.sqrt(A.multiply(A).sum(axis=1).A1)
    B_norm = np.sqrt(B.multiply(B).sum(axis=1).A1)

    denom = A_norm * B_norm
    out = np.zeros_like(numer, dtype=float)

    mask = denom != 0
    out[mask] = numer[mask] / denom[mask]

    return out


def tfidf_cosine_pair(vectorizer, a: str, b: str) -> float:
    try:
        vecs = vectorizer.transform([safe_text(a), safe_text(b)])
        score = paired_cosine_sparse(vecs[0], vecs[1])[0]
        return float(score)
    except Exception:
        return 0.0


# ============================================================
# Model A feature helpers
# ============================================================

def count_overlap_words(a: str, b: str) -> int:
    a_words = set(content_words(a))
    b_words = set(content_words(b))
    return len(a_words & b_words)


def build_model_a_numeric_features(article: str, question: str, option: str, vectorizer) -> list[float]:
    """
    Exact 11 numeric features expected by numeric_scaler.pkl.

    Feature order is based on model_a_train_features_full.csv:
    1. cos_article_option
    2. cos_question_option
    3. cos_article_question
    4. article_len
    5. question_len
    6. option_len
    7. question_option_overlap
    8. article_option_overlap
    9. article_question_overlap
    10. question_option_overlap_ratio
    11. article_option_overlap_ratio
    """
    article = safe_text(article)
    question = safe_text(question)
    option = safe_text(option)

    article_words = content_words(article)
    question_words = content_words(question)
    option_words = content_words(option)

    article_len = len(article_words)
    question_len = len(question_words)
    option_len = len(option_words)

    question_option_overlap = count_overlap_words(question, option)
    article_option_overlap = count_overlap_words(article, option)
    article_question_overlap = count_overlap_words(article, question)

    question_option_overlap_ratio = (
        question_option_overlap / option_len if option_len > 0 else 0.0
    )

    article_option_overlap_ratio = (
        article_option_overlap / option_len if option_len > 0 else 0.0
    )

    features = [
        tfidf_cosine_pair(vectorizer, article, option),
        tfidf_cosine_pair(vectorizer, question, option),
        tfidf_cosine_pair(vectorizer, article, question),
        article_len,
        question_len,
        option_len,
        question_option_overlap,
        article_option_overlap,
        article_question_overlap,
        question_option_overlap_ratio,
        article_option_overlap_ratio,
    ]

    return [float(x) for x in features]


def make_model_a_verifier_input(article: str, question: str, option: str, model_a: dict):
    vectorizer = model_a.get("vectorizer")
    scaler = model_a.get("numeric_scaler")
    verifier = model_a.get("verifier")

    if vectorizer is None or scaler is None or verifier is None:
        return None

    input_text = safe_text(article) + " " + safe_text(question) + " " + safe_text(option)

    X_tfidf = vectorizer.transform([input_text])

    numeric = build_model_a_numeric_features(
        article=article,
        question=question,
        option=option,
        vectorizer=vectorizer,
    )

    X_num = np.array([numeric], dtype=float)

    expected_scaler_features = getattr(scaler, "n_features_in_", None)
    if expected_scaler_features is not None and X_num.shape[1] != expected_scaler_features:
        print(
            f"[Model A] Numeric feature mismatch. "
            f"Scaler expects {expected_scaler_features}, built {X_num.shape[1]}."
        )
        return None

    X_num_scaled = scaler.transform(X_num)

    X_combined = hstack([X_tfidf, X_num_scaled])

    expected_verifier_features = getattr(verifier, "n_features_in_", None)
    if expected_verifier_features is not None and X_combined.shape[1] != expected_verifier_features:
        print(
            f"[Model A] Combined feature mismatch. "
            f"Verifier expects {expected_verifier_features}, built {X_combined.shape[1]}."
        )
        return None

    return X_combined


# ============================================================
# Model B distractor helpers
# ============================================================

def generate_ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def extract_candidate_phrases(
    article: str,
    question: str | None = None,
    correct_answer: str | None = None,
    max_candidates: int = 80,
) -> list[str]:
    """
    Same inference-style extraction used for Model B:
    unigrams, bigrams, trigrams, frequency-ranked content phrases.
    """
    article_norm = normalize_text(article)
    question_norm = normalize_text(question)
    answer_norm = normalize_text(correct_answer)

    tokens = content_words(article_norm)

    unigrams = tokens
    bigrams = generate_ngrams(tokens, 2)
    trigrams = generate_ngrams(tokens, 3)

    all_candidates = unigrams + bigrams + trigrams
    counts = Counter(all_candidates)

    cleaned = []
    seen = set()

    for cand, _freq in counts.most_common():
        cand_norm = normalize_text(cand)

        if cand_norm in seen:
            continue
        if len(cand_norm) < 3:
            continue
        if cand_norm == answer_norm:
            continue
        if answer_norm and cand_norm in answer_norm:
            continue
        if answer_norm and answer_norm in cand_norm:
            continue
        if answer_norm and word_overlap(cand_norm, answer_norm) >= 0.85:
            continue
        if question_norm and cand_norm == question_norm:
            continue

        cleaned.append(cand_norm)
        seen.add(cand_norm)

        if len(cleaned) >= max_candidates:
            break

    return cleaned


def build_model_b_candidate_features(
    article: str,
    question: str,
    correct_answer: str,
    candidates: list[str],
    vectorizer,
) -> pd.DataFrame:
    if not candidates:
        return pd.DataFrame(columns=MODEL_B_FEATURE_COLS)

    articles = [safe_text(article)] * len(candidates)
    questions = [safe_text(question)] * len(candidates)
    answers = [safe_text(correct_answer)] * len(candidates)

    cand_vec = vectorizer.transform(candidates)
    ans_vec = vectorizer.transform(answers)
    ques_vec = vectorizer.transform(questions)
    art_vec = vectorizer.transform(articles)

    cos_candidate_answer = paired_cosine_sparse(cand_vec, ans_vec)
    cos_candidate_question = paired_cosine_sparse(cand_vec, ques_vec)
    cos_candidate_article = paired_cosine_sparse(cand_vec, art_vec)

    rows = []

    for i, candidate in enumerate(candidates):
        cand_words = content_words(candidate)
        ans_words = content_words(correct_answer)

        rows.append({
            "cos_candidate_answer": float(cos_candidate_answer[i]),
            "cos_candidate_question": float(cos_candidate_question[i]),
            "cos_candidate_article": float(cos_candidate_article[i]),
            "candidate_word_len": len(cand_words),
            "answer_word_len": len(ans_words),
            "length_diff": abs(len(cand_words) - len(ans_words)),
            "char_overlap_answer": char_overlap(candidate, correct_answer),
            "word_overlap_answer": word_overlap(candidate, correct_answer),
            "word_overlap_question": word_overlap(candidate, question),
            "candidate_frequency_article": candidate_frequency_in_article(candidate, article),
            "candidate_in_question": int(normalize_text(candidate) in normalize_text(question)),
            "candidate_same_as_answer": int(normalize_text(candidate) == normalize_text(correct_answer)),
            "candidate_contains_answer": int(normalize_text(correct_answer) in normalize_text(candidate)),
            "answer_contains_candidate": int(normalize_text(candidate) in normalize_text(correct_answer)),
        })

    return pd.DataFrame(rows, columns=MODEL_B_FEATURE_COLS)


def select_diverse_top_n(
    candidates: list[str],
    scores: list[float],
    correct_answer: str,
    n: int = 3,
    diversity_threshold: float = 0.25,
) -> list[str]:
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

    selected = []

    for cand, _score in ranked:
        cand = safe_text(cand).strip()

        if not cand:
            continue

        if normalize_text(cand) == normalize_text(correct_answer):
            continue

        if normalize_text(cand) in [normalize_text(x) for x in selected]:
            continue

        too_similar = False

        for chosen in selected:
            if word_overlap(cand, chosen) >= diversity_threshold:
                too_similar = True
                break

        if too_similar:
            continue

        selected.append(cand)

        if len(selected) == n:
            break

    # Fallback if diversity filtering is too strict.
    if len(selected) < n:
        for cand, _score in ranked:
            cand = safe_text(cand).strip()

            if not cand:
                continue

            if normalize_text(cand) == normalize_text(correct_answer):
                continue

            if normalize_text(cand) in [normalize_text(x) for x in selected]:
                continue

            selected.append(cand)

            if len(selected) == n:
                break

    return selected[:n]


# ============================================================
# Hint helpers
# ============================================================

def mask_answer_in_sentence(sentence: str, answer: str) -> str:
    sentence = safe_text(sentence)
    answer = safe_text(answer)

    if not answer.strip():
        return sentence

    pattern = re.compile(re.escape(answer), re.IGNORECASE)
    masked = pattern.sub("[ANSWER]", sentence)

    # If exact answer phrase was not found, mask content words.
    if masked == sentence:
        for word in content_words(answer):
            masked = re.sub(
                rf"\b{re.escape(word)}\b",
                "[ANSWER]",
                masked,
                flags=re.IGNORECASE,
            )

    return masked


def build_hint_sentence_features(
    article: str,
    question: str,
    correct_answer: str,
    vectorizer,
) -> tuple[pd.DataFrame, list[str]]:
    sentences = split_sentences(article)

    if not sentences:
        sentences = [safe_text(article)[:200] if article else "Refer to the passage."]

    question = safe_text(question)
    correct_answer = safe_text(correct_answer)
    combined_query = question + " " + correct_answer

    sent_vec = vectorizer.transform(sentences)
    q_vec = vectorizer.transform([question] * len(sentences))
    a_vec = vectorizer.transform([correct_answer] * len(sentences))
    qa_vec = vectorizer.transform([combined_query] * len(sentences))

    cos_q = paired_cosine_sparse(sent_vec, q_vec)
    cos_a = paired_cosine_sparse(sent_vec, a_vec)
    cos_qa = paired_cosine_sparse(sent_vec, qa_vec)

    rows = []

    for i, sentence in enumerate(sentences):
        rows.append({
            "cos_question_sentence": float(cos_q[i]),
            "cos_answer_sentence": float(cos_a[i]),
            "cos_question_answer_sentence": float(cos_qa[i]),
            "question_sentence_overlap": word_overlap(question, sentence),
            "answer_sentence_overlap": word_overlap(correct_answer, sentence),
            "sentence_position_norm": i / max(1, len(sentences) - 1),
            "sentence_word_len": len(content_words(sentence)),
            "contains_correct_answer": int(
                normalize_text(correct_answer) in normalize_text(sentence)
            ),
        })

    return pd.DataFrame(rows, columns=HINT_FEATURE_COLS), sentences


# ============================================================
# Model A — QGen helpers
# ============================================================

def infer_answer_type(answer: str) -> str:
    answer_l = normalize_text(answer)

    if re.search(r"\b(who|person|people|man|woman|boy|girl|teacher|student|father|mother|mr|mrs|miss)\b", answer_l):
        return "who"

    if re.search(r"\b(school|city|country|hospital|home|room|place|park|river|street|station|store|shop)\b", answer_l):
        return "where"

    if re.search(r"\b(day|year|month|morning|evening|night|today|yesterday|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", answer_l):
        return "when"

    return "what"


def infer_wh_type(question: str) -> str:
    q = normalize_text(question)

    for wh in ["who", "what", "where", "when", "why", "how", "which"]:
        if q.startswith(wh) or f" {wh} " in f" {q} ":
            return wh

    return "what"


def make_cloze_sentence(sentence: str, answer: str) -> str:
    sentence = safe_text(sentence)
    answer = safe_text(answer)

    if answer and normalize_text(answer) in normalize_text(sentence):
        pattern = re.compile(re.escape(answer), re.IGNORECASE)
        return pattern.sub("_", sentence)

    masked = sentence
    changed = False

    for word in content_words(answer):
        new_masked = re.sub(rf"\b{re.escape(word)}\b", "_", masked, flags=re.IGNORECASE)
        if new_masked != masked:
            changed = True
        masked = new_masked

    if changed:
        return masked

    return sentence


def generate_qgen_template_candidates(
    article: str,
    correct_answer: str,
    qgen_vectorizer,
    max_sentences: int = 6,
) -> list[dict]:
    """
    Build candidate questions using the same style of templates seen in
    qgen_train_candidates.csv:
    - cloze_completion
    - according_to_true
    - what_information
    - who/where/when/how generic templates
    """
    sentences = split_sentences(article)

    if not sentences:
        sentences = [safe_text(article)[:200] if article else "The passage gives information."]

    correct_answer = safe_text(correct_answer)
    answer_type = infer_answer_type(correct_answer)

    sent_vec = qgen_vectorizer.transform(sentences)
    ans_vec = qgen_vectorizer.transform([correct_answer] * len(sentences))
    scores = paired_cosine_sparse(sent_vec, ans_vec)

    ranked_indices = list(np.argsort(scores)[::-1])
    ranked_indices = ranked_indices[:max_sentences]

    candidates = []

    for idx in ranked_indices:
        source_sentence = safe_text(sentences[idx])
        sentence_score = float(scores[idx])
        contains_answer = int(
            normalize_text(correct_answer) in normalize_text(source_sentence)
        )

        cloze_sentence = make_cloze_sentence(source_sentence, correct_answer)

        template_items = [
            {
                "template_name": "cloze_completion",
                "wh_type": "what",
                "generated_question": f"What completes this statement: {cloze_sentence}?",
            },
            {
                "template_name": "according_to_true",
                "wh_type": "which",
                "generated_question": "Which of the following is true according to the passage?",
            },
            {
                "template_name": "what_information",
                "wh_type": "what",
                "generated_question": "What information is given in the passage?",
            },
        ]

        if answer_type == "who":
            template_items.append({
                "template_name": "who_template",
                "wh_type": "who",
                "generated_question": "Who is mentioned in the passage?",
            })

        if answer_type == "where":
            template_items.append({
                "template_name": "where_template",
                "wh_type": "where",
                "generated_question": "Where does the passage say this happened?",
            })

        if answer_type == "when":
            template_items.append({
                "template_name": "when_template",
                "wh_type": "when",
                "generated_question": "When does the passage say this happened?",
            })

        template_items.append({
            "template_name": "how_template",
            "wh_type": "how",
            "generated_question": "How is this described in the passage?",
        })

        for item in template_items:
            candidates.append({
                "source_sentence": source_sentence,
                "sentence_position": idx,
                "sentence_score": sentence_score,
                "contains_answer": contains_answer,
                "template_name": item["template_name"],
                "wh_type": item["wh_type"],
                "answer_type": answer_type,
                "generated_question": item["generated_question"],
            })

    return candidates


def build_qgen_features(
    article: str,
    correct_answer: str,
    candidates: list[dict],
    qgen_vectorizer,
) -> pd.DataFrame:
    rows = []

    article = safe_text(article)
    correct_answer = safe_text(correct_answer)

    for cand in candidates:
        source_sentence = safe_text(cand["source_sentence"])
        generated_question = safe_text(cand["generated_question"])

        generated_q_len = len(content_words(generated_question))
        source_sentence_len = len(content_words(source_sentence))
        correct_answer_len = len(content_words(correct_answer))

        q_sent_overlap = count_overlap_words(generated_question, source_sentence)
        q_ans_overlap = count_overlap_words(generated_question, correct_answer)

        q_sent_overlap_ratio = (
            q_sent_overlap / source_sentence_len if source_sentence_len > 0 else 0.0
        )

        q_ans_overlap_ratio = (
            q_ans_overlap / correct_answer_len if correct_answer_len > 0 else 0.0
        )

        wh_type = safe_text(cand.get("wh_type", "what")).lower()
        answer_type = safe_text(cand.get("answer_type", "what")).lower()
        template_name = safe_text(cand.get("template_name", "")).lower()

        row = {
            "sentence_score": float(cand.get("sentence_score", 0.0)),
            "contains_answer": int(cand.get("contains_answer", 0)),
            "sentence_position": int(cand.get("sentence_position", 0)),
            "generated_q_len": generated_q_len,
            "source_sentence_len": source_sentence_len,
            "correct_answer_len": correct_answer_len,
            "q_sent_overlap": q_sent_overlap,
            "q_ans_overlap": q_ans_overlap,
            "q_sent_overlap_ratio": q_sent_overlap_ratio,
            "q_ans_overlap_ratio": q_ans_overlap_ratio,
            "cos_q_sent": tfidf_cosine_pair(qgen_vectorizer, generated_question, source_sentence),
            "cos_q_ans": tfidf_cosine_pair(qgen_vectorizer, generated_question, correct_answer),
            "cos_q_ctx": tfidf_cosine_pair(qgen_vectorizer, generated_question, article),

            "wh_who": int(wh_type == "who"),
            "wh_what": int(wh_type == "what"),
            "wh_where": int(wh_type == "where"),
            "wh_when": int(wh_type == "when"),
            "wh_why": int(wh_type == "why"),
            "wh_how": int(wh_type == "how"),
            "wh_which": int(wh_type == "which"),

            "answer_type_who": int(answer_type == "who"),
            "answer_type_what": int(answer_type == "what"),
            "answer_type_where": int(answer_type == "where"),
            "answer_type_when": int(answer_type == "when"),

            "template_is_cloze": int(template_name == "cloze_completion"),
            "template_is_according": int(template_name == "according_to_true"),
            "template_is_generic": int(
                template_name not in ["cloze_completion", "according_to_true"]
            ),
        }

        rows.append(row)

    return pd.DataFrame(rows, columns=QGEN_FEATURE_COLS)


def score_qgen_candidates(candidates: list[dict], features_df: pd.DataFrame, qgen_ranker) -> list[float]:
    if len(candidates) == 0 or features_df.empty:
        return []

    X = features_df[QGEN_FEATURE_COLS]

    if hasattr(qgen_ranker, "decision_function"):
        raw_scores = qgen_ranker.decision_function(X)
        return [float(x) for x in np.ravel(raw_scores)]

    if hasattr(qgen_ranker, "predict_proba"):
        return [float(x) for x in qgen_ranker.predict_proba(X)[:, 1]]

    preds = qgen_ranker.predict(X)
    return [float(x) for x in preds]


# ============================================================
# Model A — Question & Answer Generator / Verifier
# ============================================================

def generate_question_and_answer(article: str) -> dict:
    """
    Generate a question and identify the correct answer.

    RACE article (found in test.csv):
        → Return gold question + gold answer directly. No QGen needed.
          Model B still generates fresh distractors and hints.
          Model A verifier is still called when user checks answer.

    Custom pasted article (not in test.csv):
        → Run Model A QGen pipeline (template candidates + ranker).
          Fall back to generic question if ranker unavailable or fails.
    """
    start = time.time()

    sample = lookup_sample_by_article(article)

    # ── Path 1: RACE article ──────────────────────────────────────────────
    if sample is not None:
        sample_question = safe_text(sample.get("question", "")).strip()
        sample_correct_answer = safe_text(sample.get("correct_answer", "")).strip()
        sample_gold_label = safe_text(sample.get("gold_answer_label", "A")).strip() or "A"

        if sample_question and sample_correct_answer:
            return {
                "question": sample_question,
                "correct_answer_text": sample_correct_answer,
                "correct_label": sample_gold_label,
                "latency": time.time() - start,
            }

    # ── Path 2: Custom article — run Model A QGen pipeline ───────────────
    model_a = load_model_a()

    sentences = split_sentences(article)
    correct_answer_text = (
        max(sentences, key=len)[:120] if sentences
        else "The passage describes an important idea."
    )

    if (
        model_a is not None
        and "qgen_vectorizer" in model_a
        and "qgen_ranker" in model_a
    ):
        try:
            qgen_vectorizer = model_a["qgen_vectorizer"]
            qgen_ranker = model_a["qgen_ranker"]

            candidates = generate_qgen_template_candidates(
                article=article,
                correct_answer=correct_answer_text,
                qgen_vectorizer=qgen_vectorizer,
                max_sentences=6,
            )

            features_df = build_qgen_features(
                article=article,
                correct_answer=correct_answer_text,
                candidates=candidates,
                qgen_vectorizer=qgen_vectorizer,
            )

            expected_features = getattr(qgen_ranker, "n_features_in_", None)
            if expected_features is not None and features_df.shape[1] != expected_features:
                raise ValueError(
                    f"QGen feature mismatch: ranker expects {expected_features}, "
                    f"built {features_df.shape[1]}"
                )

            scores = score_qgen_candidates(candidates, features_df, qgen_ranker)

            if scores:
                best_idx = int(np.argmax(scores))
                return {
                    "question": safe_text(candidates[best_idx]["generated_question"]).strip(),
                    "correct_answer_text": correct_answer_text,
                    "correct_label": "A",
                    "latency": time.time() - start,
                }

        except Exception as e:
            print(f"[Model A] QGen inference failed: {e}")

    # ── Fallback: generic question ────────────────────────────────────────
    return {
        "question": "According to the passage, which statement is correct?",
        "correct_answer_text": correct_answer_text,
        "correct_label": "A",
        "latency": time.time() - start,
    }


def verify_answer(
    article: str,
    question: str,
    selected_option_text: str,
    correct_option_text: str,
) -> dict:
    """
    Verify whether the selected option is correct.

    The UI already knows the correct option text after generating the quiz,
    so exact match is used as the final correctness signal for a stable demo.
    The trained Model A verifier is used when feature dimensions match, mainly
    to provide model-based confidence.
    """
    start = time.time()

    model_a = load_model_a()

    selected_norm = normalize_text(selected_option_text)
    correct_norm = normalize_text(correct_option_text)

    exact_is_correct = selected_norm == correct_norm

    is_correct = exact_is_correct
    confidence = 0.95 if exact_is_correct else 0.85

    if model_a is not None and "verifier" in model_a and "vectorizer" in model_a:
        try:
            X = make_model_a_verifier_input(
                article,
                question,
                selected_option_text,
                model_a,
            )

            if X is not None:
                verifier = model_a["verifier"]
                pred = int(verifier.predict(X)[0])

                # Keep correctness stable using known correct option.
                # Use model prediction to adjust confidence.
                if hasattr(verifier, "predict_proba"):
                    proba = verifier.predict_proba(X)[0]
                    model_conf = float(np.max(proba))
                elif hasattr(verifier, "decision_function"):
                    score = verifier.decision_function(X)
                    if isinstance(score, np.ndarray):
                        score = float(np.ravel(score)[0])
                    model_conf = sigmoid(abs(float(score)))
                else:
                    model_conf = 0.75

                if pred == 1 and exact_is_correct:
                    confidence = max(0.90, model_conf)
                elif pred == 0 and not exact_is_correct:
                    confidence = max(0.80, model_conf)
                else:
                    confidence = 0.70
        except Exception as e:
            print(f"[Model A] Verifier inference failed: {e}")

    latency = time.time() - start

    return {
        "is_correct": bool(is_correct),
        "confidence": float(confidence),
        "latency": latency,
    }


# ============================================================
# Model B — Distractor & Hint Generator
# ============================================================

def generate_distractors(
    article: str,
    question: str,
    correct_answer: str,
    n: int = 3,
) -> dict:
    """
    Generate n plausible-but-incorrect distractor options using
    the trained Random Forest distractor ranker.
    """
    start = time.time()

    model_b = load_model_b()

    if (
        model_b is None
        or "vectorizer" not in model_b
        or "distractor_ranker" not in model_b
    ):
        sentences = split_sentences(article)
        fallback = [
            s[:120]
            for s in sentences
            if normalize_text(s[:120]) != normalize_text(correct_answer)
        ]

        random.shuffle(fallback)
        distractors = fallback[:n]

        while len(distractors) < n:
            distractors.append(
                f"This option is not supported by the passage. ({len(distractors) + 1})"
            )

        latency = time.time() - start
        return {"distractors": distractors[:n], "latency": latency}

    vectorizer = model_b["vectorizer"]
    ranker = model_b["distractor_ranker"]

    candidates = extract_candidate_phrases(
        article=article,
        question=question,
        correct_answer=correct_answer,
        max_candidates=80,
    )

    if not candidates:
        latency = time.time() - start
        return {
            "distractors": [
                "This option is not supported by the passage.",
                "This choice is unrelated to the main idea.",
                "This statement is not confirmed by the text.",
            ][:n],
            "latency": latency,
        }

    try:
        X = build_model_b_candidate_features(
            article=article,
            question=question,
            correct_answer=correct_answer,
            candidates=candidates,
            vectorizer=vectorizer,
        )

        if hasattr(ranker, "predict_proba"):
            scores = ranker.predict_proba(X[MODEL_B_FEATURE_COLS])[:, 1]
        elif hasattr(ranker, "decision_function"):
            raw_scores = ranker.decision_function(X[MODEL_B_FEATURE_COLS])
            scores = np.array([sigmoid(x) for x in raw_scores])
        else:
            preds = ranker.predict(X[MODEL_B_FEATURE_COLS])
            scores = np.array(preds, dtype=float)

        distractors = select_diverse_top_n(
            candidates=candidates,
            scores=list(scores),
            correct_answer=correct_answer,
            n=n,
            diversity_threshold=0.25,
        )

    except Exception as e:
        print(f"[Model B] Distractor inference failed: {e}")
        distractors = []

    while len(distractors) < n:
        distractors.append(
            f"This option is not supported by the passage. ({len(distractors) + 1})"
        )

    latency = time.time() - start

    return {
        "distractors": distractors[:n],
        "latency": latency,
    }


def generate_hints(article: str, question: str, correct_answer: str) -> dict:
    """
    Generate 3 graduated hints using the trained Logistic Regression hint scorer.

    Hint 1: general keyword clue
    Hint 2: relevant sentence with answer masked
    Hint 3: stronger supporting context with answer masked
    """
    start = time.time()

    model_b = load_model_b()

    if (
        model_b is None
        or "vectorizer" not in model_b
        or "hint_scorer" not in model_b
    ):
        sentences = split_sentences(article)

        if not sentences:
            sentences = [article[:200] if article else "Refer to the passage."]

        first_words = " ".join(article.split()[:25])
        middle_sentence = sentences[len(sentences) // 2] if len(sentences) > 1 else sentences[0]

        hints = [
            f"Focus on the main topic introduced in the passage: \"{first_words}...\"",
            f"Pay close attention to this part of the passage: \"{middle_sentence[:140]}\"",
            f"The answer is connected to the idea: \"{correct_answer[:80]}...\"",
        ]

        latency = time.time() - start
        return {"hints": hints, "latency": latency}

    vectorizer = model_b["vectorizer"]
    hint_scorer = model_b["hint_scorer"]

    try:
        X_hint, sentences = build_hint_sentence_features(
            article=article,
            question=question,
            correct_answer=correct_answer,
            vectorizer=vectorizer,
        )

        if hasattr(hint_scorer, "predict_proba"):
            scores = hint_scorer.predict_proba(X_hint[HINT_FEATURE_COLS])[:, 1]
        elif hasattr(hint_scorer, "decision_function"):
            raw_scores = hint_scorer.decision_function(X_hint[HINT_FEATURE_COLS])
            scores = np.array([sigmoid(x) for x in raw_scores])
        else:
            preds = hint_scorer.predict(X_hint[HINT_FEATURE_COLS])
            scores = np.array(preds, dtype=float)

        best_idx = int(np.argmax(scores))
        best_sentence = safe_text(sentences[best_idx])

    except Exception as e:
        print(f"[Model B] Hint inference failed: {e}")
        sentences = split_sentences(article)
        best_sentence = sentences[0] if sentences else safe_text(article)[:200]

    q_keywords = content_words(question)
    keyword_text = ", ".join(q_keywords[:5]) if q_keywords else "the important words in the question"

    masked_sentence = mask_answer_in_sentence(best_sentence, correct_answer)

    hint1 = f"Focus on the part of the passage related to: {keyword_text}."
    hint2 = f"A relevant sentence says: {masked_sentence}"
    hint3 = f"The answer is supported by this context: {masked_sentence}"

    hints = [hint1, hint2, hint3]

    latency = time.time() - start

    return {
        "hints": hints,
        "latency": latency,
    }


# ============================================================
# Combined inference
# ============================================================

def run_full_inference(
    article: str,
    question: str | None = None,
    correct_answer: str | None = None,
) -> dict:
    """
    Run Model A and Model B for a given article.

    Backwards compatible:
    - Existing UI can call run_full_inference(article)
    - Improved UI can call run_full_inference(article, question, correct_answer)

    If question/correct_answer are not provided, the function attempts to recover
    them from data/raw/test.csv by article lookup.
    """
    overall_start = time.time()

    if question and correct_answer:
        a_out = {
            "question": safe_text(question),
            "correct_answer_text": safe_text(correct_answer),
            "correct_label": "A",
            "latency": 0.0,
        }
    else:
        a_out = generate_question_and_answer(article)

    question_text = safe_text(a_out["question"])
    correct_text = safe_text(a_out["correct_answer_text"])

    d_out = generate_distractors(article, question_text, correct_text, n=3)
    h_out = generate_hints(article, question_text, correct_text)

    pool = [(correct_text, True)] + [(d, False) for d in d_out["distractors"]]
    random.shuffle(pool)

    labels = ["A", "B", "C", "D"]
    options = {}
    correct_label = "A"

    for label, (text, is_correct) in zip(labels, pool):
        options[label] = text
        if is_correct:
            correct_label = label

    total_latency = time.time() - overall_start

    return {
        "question": question_text,
        "options": options,
        "correct_label": correct_label,
        "correct_answer_text": correct_text,
        "hints": h_out["hints"],
        "total_latency": total_latency,
        "model_a_latency": float(a_out.get("latency", 0.0)),
        "model_b_latency": float(d_out["latency"] + h_out["latency"]),
    }