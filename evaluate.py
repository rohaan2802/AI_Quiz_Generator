"""
NLP generation evaluation metrics: BLEU, ROUGE, METEOR.

These are the metrics required by the project (text-generation task), replacing
classification metrics like Accuracy/Precision/Recall.

Each function compares a *generated* text (hypothesis) against a *reference*
text and returns a score in [0, 1].
"""
from __future__ import annotations
import warnings

# Suppress harmless NLTK download warnings during the first call
warnings.filterwarnings("ignore", category=UserWarning)

# ---------- NLTK setup (BLEU + METEOR) ----------
try:
    import nltk
    from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
    from nltk.translate.meteor_score import meteor_score as _meteor

    # Ensure required NLTK resources exist (downloads only on first run)
    for resource in ["punkt", "punkt_tab", "wordnet", "omw-1.4"]:
        try:
            nltk.data.find(resource)
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
            except Exception:
                pass
    _NLTK_OK = True
except ImportError:
    _NLTK_OK = False

# ---------- ROUGE setup ----------
try:
    from rouge_score import rouge_scorer
    _ROUGE_OK = True
    _rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
except ImportError:
    _ROUGE_OK = False
    _rouge = None


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer (fallback when NLTK unavailable)."""
    return text.lower().split()


# =========================================================================
# BLEU
# =========================================================================
def bleu_score(reference: str, hypothesis: str) -> float:
    """
    Compute BLEU-4 score between a single reference and hypothesis.

    Uses smoothing (method1) so short sentences don't get a hard zero from
    missing higher-order n-grams.
    """
    if not reference or not hypothesis:
        return 0.0
    ref_tokens = [_tokenize(reference)]
    hyp_tokens = _tokenize(hypothesis)
    if not _NLTK_OK:
        # Fallback: simple unigram overlap ratio
        ref_set = set(ref_tokens[0])
        hyp_set = set(hyp_tokens)
        if not hyp_set:
            return 0.0
        return len(ref_set & hyp_set) / len(hyp_set)
    try:
        smoothie = SmoothingFunction().method1
        return sentence_bleu(ref_tokens, hyp_tokens,
                             weights=(0.25, 0.25, 0.25, 0.25),
                             smoothing_function=smoothie)
    except Exception:
        return 0.0


# =========================================================================
# ROUGE
# =========================================================================
def rouge_scores(reference: str, hypothesis: str) -> dict:
    """
    Compute ROUGE-1, ROUGE-2, ROUGE-L F-measures.

    Returns:
        {"rouge1": float, "rouge2": float, "rougeL": float}
    """
    if not reference or not hypothesis:
        return {"rouge1": 0.0, "rouge2": 0.0, "rougeL": 0.0}
    if not _ROUGE_OK:
        # Fallback: unigram overlap as a crude proxy
        overlap = bleu_score(reference, hypothesis)
        return {"rouge1": overlap, "rouge2": overlap * 0.5, "rougeL": overlap}
    try:
        scores = _rouge.score(reference, hypothesis)
        return {
            "rouge1": scores["rouge1"].fmeasure,
            "rouge2": scores["rouge2"].fmeasure,
            "rougeL": scores["rougeL"].fmeasure,
        }
    except Exception:
        return {"rouge1": 0.0, "rouge2": 0.0, "rougeL": 0.0}


# =========================================================================
# METEOR
# =========================================================================
def meteor_score(reference: str, hypothesis: str) -> float:
    """
    Compute METEOR score, accounting for synonyms and stemming.
    """
    if not reference or not hypothesis:
        return 0.0
    if not _NLTK_OK:
        # Fallback: token overlap ratio
        ref_set = set(_tokenize(reference))
        hyp_set = set(_tokenize(hypothesis))
        if not (ref_set | hyp_set):
            return 0.0
        return len(ref_set & hyp_set) / len(ref_set | hyp_set)
    try:
        return _meteor([_tokenize(reference)], _tokenize(hypothesis))
    except Exception:
        # Often fails if WordNet not downloaded — fallback to overlap
        ref_set = set(_tokenize(reference))
        hyp_set = set(_tokenize(hypothesis))
        if not (ref_set | hyp_set):
            return 0.0
        return len(ref_set & hyp_set) / len(ref_set | hyp_set)


# =========================================================================
# Convenience: compute all three at once
# =========================================================================
def compute_all(reference: str, hypothesis: str) -> dict:
    """
    Compute BLEU, ROUGE-1/2/L, and METEOR in one call.

    Returns:
        {
            "bleu": float,
            "rouge1": float,
            "rouge2": float,
            "rougeL": float,
            "meteor": float,
        }
    """
    rouge = rouge_scores(reference, hypothesis)
    return {
        "bleu":   bleu_score(reference, hypothesis),
        "rouge1": rouge["rouge1"],
        "rouge2": rouge["rouge2"],
        "rougeL": rouge["rougeL"],
        "meteor": meteor_score(reference, hypothesis),
    }
