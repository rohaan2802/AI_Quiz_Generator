# Notebook Analysis — RACE Intelligent Quiz System

## Quick Reference

| Notebook | Role | Best Algorithm | Key Metric (Test METEOR) |
|---|---|---|---|
| Model_A_Full | Answer Verifier + QGen v1 | LinearSVC + Combined | Verifier: 0.440 / QGen: 0.160 |
| Model_A_Improvements_v2 | Unsupervised + QGen v2 | LinearSVC Ranker v2 | QGen v2: 0.156 (slight regression) |
| Model_B | Distractor + Hint Ranker | RF (distractor) / LR (hint) | Distractor: 0.762 / Hint: 0.687 |
| ModelBfinal | True Novel Distractor Gen | RF (same as above) | 0.024 — reveals real difficulty |

---

## Notebook 1 — `Model_A_Full.ipynb`

### Purpose
Full end-to-end training of Model A on the complete RACE dataset (~100K questions). Trains two components:
1. **Answer Verifier** — classifies whether a (article, question, option) triple is the correct answer
2. **Question Generator (QGen v1)** — ranks template-generated candidate questions against the gold question

### Dataset
- Source: RACE (Kaggle) — train/val/test split
- Per-option expansion: each question × 4 options → 4 rows (1 positive, 3 negative)
- **Train:** 281,120 rows | **Val:** 35,140 rows | **Test:** 35,144 rows
- Class balance: 75% negative / 25% positive (severely imbalanced)

### Features

**TF-IDF (50,000 vocab)**
- Input: concatenated `article + question + option`
- Params: `min_df=5`, `max_df=0.95`, `ngram_range=(1,2)`

**11 Numeric/Lexical Features** (scaled with StandardScaler)
| Feature | Description |
|---|---|
| cos_article_option | Cosine similarity between article and option |
| cos_question_option | Cosine similarity between question and option |
| cos_article_question | Cosine similarity between article and question |
| article_len | Token count of article |
| question_len | Token count of question |
| option_len | Token count of option |
| question_option_overlap | Shared content word count |
| article_option_overlap | Shared content word count |
| article_question_overlap | Shared content word count |
| question_option_overlap_ratio | Jaccard ratio |
| article_option_overlap_ratio | Jaccard ratio |

**Combined:** TF-IDF (50,000 dims) + scaled numeric (11 dims) = 50,011 features

### Models Trained — Answer Verifier

| Model | Val F1 (option-level) |
|---|---|
| Logistic Regression + TF-IDF | 0.4945 |
| LinearSVC + TF-IDF | 0.5031 |
| Naive Bayes + TF-IDF | 0.4286 |
| Random Forest + Numeric only | 0.4632 |
| Logistic Regression + Combined | 0.5081 |
| **LinearSVC + Combined** | **0.5176** ✅ SELECTED |
| Hard Voting Ensemble | 0.5151 |

### Results — Answer Verifier (Test Set)

**LinearSVC + Combined Features:**
| Metric | Score |
|---|---|
| Question-level accuracy | **0.3732** |
| BLEU-1 | 0.4806 |
| BLEU-2 | 0.4035 |
| BLEU-4 | 0.3325 |
| ROUGE-1 F1 | 0.5043 |
| ROUGE-2 F1 | 0.3746 |
| ROUGE-L F1 | 0.4971 |
| METEOR | **0.4400** |

> **Note:** Random chance on a 4-way MCQ is 0.25. Model achieves 0.373 — meaningful but limited improvement. BLEU/ROUGE are measured against the gold correct option text.

### Models Trained — QGen v1

- **Candidate generation:** top-2 relevant sentences (TF-IDF cosine to correct answer) × templates
- **Pseudo-labels:** weighted score = BLEU-1×0.30 + BLEU-2×0.20 + ROUGE-L×0.25 + METEOR×0.25 vs gold question
- **Templates (v1):** `cloze_completion`, `according_to_true`, `what_information`, wh-type (who/where/when)

**Rankers:**
- LinearSVC Ranker ✅ SELECTED
- Random Forest Ranker (n_estimators=200)

### Results — QGen v1 (Test Set)

| Configuration | BLEU-1 | BLEU-4 | ROUGE-L | METEOR |
|---|---|---|---|---|
| Baseline (template only, no ranker) | 0.1185 | 0.0238 | 0.1700 | 0.0914 |
| Random Forest Ranker | — | — | — | — |
| **LinearSVC Ranker** | **0.1811** | **0.0607** | **0.2091** | **0.1598** |

> **Gain vs baseline:** +52.8% METEOR, +24.1% BLEU-1. The ranker meaningfully improves over naive template selection.

### Unsupervised Component — K-Means (k=2)
- Features: TF-IDF sparse matrix
- Purity: **0.75** | Silhouette: **0.0062**
- Low silhouette is expected — TF-IDF clusters by topic, not correctness

### Files Saved
```
models/model_a/traditional/
├── vectorizer.pkl              # TF-IDF vectorizer (50K vocab)
├── answer_verifier.pkl         # LinearSVC + Combined (SELECTED)
├── numeric_scaler.pkl          # StandardScaler for 11 numeric features
├── qgen_vectorizer.pkl         # TF-IDF for QGen candidate scoring
└── qgen_ranker.pkl             # LinearSVC QGen ranker (SELECTED)
```

---

## Notebook 2 — `Model_A_Improvements_v2.ipynb`

### Purpose
Extends Model_A_Full without retraining base models. Adds:
1. **Unsupervised/Semi-supervised experiments** (satisfies 20-mark project requirement)
2. **QGen v2** with RACE-specific templates + 31-feature ranker

### Unsupervised: K-Means (Multiple k)

| k | Purity | Silhouette | Inertia |
|---|---|---|---|
| 4 | 0.75 | **0.00512** | 267,446 |
| 6 | 0.75 | 0.00508 | 265,651 |
| 8 | 0.75 | 0.00510 | 264,750 |

> All k values yield identical purity (0.75). K-Means on TF-IDF clusters by topic/domain, not correctness — the unsupervised structure does not align with the binary correctness label.

### Unsupervised: Gaussian Mixture Model (GMM)
- Input: 11 numeric features only (not sparse TF-IDF)
- Components: 4 | Covariance: full

| Metric | Value |
|---|---|
| Purity | 0.75 |
| Silhouette | **0.0735** |
| Log-likelihood/sample | 1.148 |
| BIC | -641,640.7 |
| AIC | -644,920.6 |

> **GMM silhouette (0.0735) >> K-Means (0.0051)** — numeric features form more coherent clusters than TF-IDF. Still, purity is tied to the majority class (75% negative).

### Semi-supervised: Label Propagation
- Subsample: 20,000 training rows
- Labeled fraction: **5%** (1,000 labeled, 19,000 unlabeled)
- Kernel: KNN, n_neighbors=10

| Model | Val Accuracy | Val F1 (macro) | Val F1 (correct class) |
|---|---|---|---|
| Label Propagation (5% labels) | 0.7357 | 0.4465 | 0.0464 |
| Supervised LR (same 20K, 100% labels) | 0.5312 | — | 0.3746 |

> LP achieves higher overall accuracy but almost zero F1 for the positive (correct) class — it collapses to predicting the majority negative class. Demonstrates the challenge of semi-supervised learning on heavily imbalanced data.

### QGen v2 — New Templates

**5 RACE-specific templates added:**
| Template | Generated Question |
|---|---|
| `inference` | "What can we infer from the passage?" |
| `not_true` | "Which of the following is NOT true according to the passage?" |
| `word_meaning` | "What does the underlined word ____ probably mean?" |
| `cloze_according_to` | "According to the passage, ____" |
| `main_idea_about` / `main_idea_title` | "What is the passage mainly about?" / "What is the best title?" |

**Template wins (which template produced the gold-closest question):**
| Template | Wins (train) |
|---|---|
| according_to_true | 14,443 |
| cloze_completion | 13,663 |
| cloze_according_to | 10,346 |
| inference | 7,445 |
| what_information | 6,460 |
| main_idea_about | 5,344 |
| main_idea_title | 4,553 |
| not_true | 4,315 |
| word_meaning | 2,739 |

**v2 Ranker:** 31 features (up from 27) — added template group one-hot encoding.

### Results — QGen v2 vs v1 (Test Set)

| Metric | v1 | v2 | Change |
|---|---|---|---|
| BLEU-1 | 0.1811 | 0.1758 | -2.9% |
| BLEU-4 | 0.0607 | 0.0597 | -1.6% |
| ROUGE-L F1 | 0.2091 | 0.2055 | -1.7% |
| METEOR | 0.1598 | 0.1564 | -2.1% |

> **v2 slightly underperforms v1.** More templates add diversity but the extra candidates dilute the ranking signal. The original 4 simple templates were already well-aligned with RACE-style questions.

### Files Saved
```
results/improvements_full/
├── unsupervised/       # KMeans, GMM, LabelProp results + metrics
└── qgen_v2/           # v2 candidate datasets, ranker models, metrics CSVs
```

---

## Notebook 3 — `Model_B.ipynb`

### Purpose
Trains Model B: the **Distractor Generator** and **Hint Generator**. Model B operates after Model A determines the correct answer — it fills in the 3 wrong options and generates passage-based hints.

### Dataset
- Same RACE data but per-question format (not per-option)
- **Train:** 70,280 questions | **Val:** 8,785 | **Test:** 8,786
- Evaluation uses top 5,000 val/test questions (computational constraint)

### TF-IDF Vectorizer (shared)
- 50,000 vocab, same parameters as Model A
- Built on (article + question + answer + other options)

### Component A: Distractor Generation

**Candidate pool:** ~18 candidates per question (top-2 article sentences × ~9 templates)
**Labels:** positive = one of 3 gold incorrect options; negative = other candidates

| Set | Total Candidates | Positive | Negative |
|---|---|---|---|
| Train | 1,288,390 | 90,000 | 1,198,390 |
| Val | 214,697 | 15,000 | 199,697 |

**14 Distractor Features:**
- cos_candidate_answer, cos_candidate_question, cos_candidate_article
- candidate_word_len, answer_word_len, length_diff
- char_overlap_answer, word_overlap_answer, word_overlap_question
- candidate_frequency_article, candidate_in_question
- candidate_same_as_answer, candidate_contains_answer, answer_contains_candidate

**Models Trained:**

| Model | Val BLEU-1 | Val ROUGE-L | Val METEOR |
|---|---|---|---|
| Logistic Regression | 0.7582 | 0.7631 | 0.7276 |
| **Random Forest (n=200)** | **0.7993** | **0.8035** | **0.7588** ✅ |

**Test Results — Random Forest:**
| Metric | Score |
|---|---|
| BLEU-1 | **0.8020** |
| BLEU-2 | 0.7526 |
| BLEU-4 | 0.6713 |
| ROUGE-1 F1 | 0.8061 |
| ROUGE-2 F1 | 0.7386 |
| ROUGE-L F1 | 0.8060 |
| METEOR | **0.7618** |

> Very high scores because the candidate pool **includes the gold distractors** — the model is largely re-ranking existing options, not generating new text.

### Component B: Hint Generation

**Candidate pool:** all article sentences per question
**Labels:** positive = sentence with highest cosine similarity to correct answer

**8 Hint Features:**
- cos_question_sentence, cos_answer_sentence, cos_question_answer_sentence
- question_sentence_overlap, answer_sentence_overlap
- sentence_position_norm, sentence_word_len, contains_correct_answer

**Model:** Logistic Regression (class_weight="balanced")

**Test Results — Classification:**
| Metric | Value |
|---|---|
| Accuracy | 0.8681 |
| Precision | 0.2871 |
| Recall | **0.8406** |
| F1 | 0.4280 |

**Test Results — BLEU/ROUGE/METEOR on selected hints:**
| Metric | Score |
|---|---|
| BLEU-1 | 0.2955 |
| BLEU-4 | 0.2570 |
| ROUGE-L F1 | 0.4337 |
| METEOR | **0.6869** |

> High METEOR (0.687) vs lower BLEU (0.296) means hints are semantically aligned with reference sentences but differ in exact wording — appropriate for paraphrase-based hints.

### Files Saved
```
models/model_b/traditional/
├── vectorizer.pkl                         # TF-IDF (50K)
├── distractor_ranker.pkl                  # Random Forest ✅
└── hint_scorer.pkl                        # Logistic Regression ✅
```

---

## Notebook 4 — `ModelBfinal.ipynb`

### Purpose
A rigorous re-evaluation of Model B that **removes gold distractors from the candidate pool**. Forces the model to generate truly novel distractors and measures real generation capability.

### Key Difference from Model_B.ipynb
After ranking candidates, any candidate that matches one of the 3 gold incorrect options is removed before final selection. Only newly generated text is kept.

| Set | Before Filtering | After Filtering | Gold Removed |
|---|---|---|---|
| Val | 377,205 | 350,850 | 26,355 |
| Test | 377,353 | 350,995 | 26,358 |

> ~7% of candidates were gold distractors being re-selected. Removing them is the correct evaluation for a generation system.

### Results — Novel Distractor Generation (Test Set)

| Metric | Model_B (with gold) | ModelBfinal (gen-only) | Drop |
|---|---|---|---|
| BLEU-1 | 0.8020 | **0.0147** | **-98.2%** |
| BLEU-4 | 0.6713 | 0.0043 | -99.4% |
| ROUGE-L F1 | 0.8060 | **0.0450** | **-94.4%** |
| METEOR | 0.7618 | **0.0238** | **-96.9%** |

> **This is the most important finding in the entire project.** The ~97% drop reveals that Model B's high scores in Model_B.ipynb were inflated by re-ranking existing gold options. When forced to generate truly novel distractors, performance collapses — the real generation task is far harder than the notebook 3 metrics suggest.

### Hint Generation (unchanged)
Identical to Model_B.ipynb — hint generation was already producing novel sentences (article sentences, not gold-copied text), so its metrics are unaffected.

| Metric | Score |
|---|---|
| BLEU-1 | 0.2955 |
| ROUGE-L F1 | 0.4337 |
| METEOR | 0.6869 |

### Files Saved
```
results/model_b_true_full/
├── val_metrics_true_distractor.csv
└── test_metrics_true_distractor.csv
```

---

## Cross-Notebook Insights

### 1. What the metrics actually mean

The inflated Model_B distractor metrics (METEOR 0.76) vs ModelBfinal (METEOR 0.02) is a lesson in evaluation design: measuring a ranker against a pool that contains the answer will always look great. The true generation quality is what ModelBfinal measures.

### 2. Combined features always win for Model A

Every comparison confirms: TF-IDF alone < Numeric alone < Combined. The 11 lexical/cosine features complement the sparse n-gram representation meaningfully.

### 3. More templates ≠ better QGen

QGen v2 adds 5 templates and 4 extra features but slightly regresses on all metrics. The original 4 templates already captured the dominant RACE question patterns (`according_to`, `cloze_completion`). Adding diversity without a stronger ranker hurts more than it helps.

### 4. GMM > K-Means for numeric features

On the 11 numeric features, GMM silhouette (0.074) dwarfs K-Means (0.005). Numeric features have meaningful Gaussian structure (cosine similarities cluster around true/false distributions) while TF-IDF is too sparse for K-Means to work well.

### 5. Semi-supervised Label Propagation pitfall

LP on 5% labels collapses to the majority class (negative/incorrect options). F1 for the positive class drops from 0.375 (supervised) to 0.046 (LP). This is a known failure mode on severely imbalanced datasets with graph-based propagation.

### 6. Model A verifier accuracy context

0.373 question-level accuracy on a 4-way MCQ (chance = 0.25) is a modest but real signal. The model correctly identifies the right answer ~37% of the time, which is meaningful for a traditional ML approach on this task without deep contextual understanding.

---

## What Is Actually Deployed in `inference.py`

| pkl file | Source notebook | Role in app |
|---|---|---|
| `model_a/traditional/vectorizer.pkl` | Model_A_Full | TF-IDF for verifier input |
| `model_a/traditional/answer_verifier.pkl` | Model_A_Full | LinearSVC — checks user's answer |
| `model_a/traditional/numeric_scaler.pkl` | Model_A_Full | Scales 11 numeric features |
| `model_a/traditional/qgen_vectorizer.pkl` | Model_A_Full | TF-IDF for QGen candidate scoring |
| `model_a/traditional/qgen_ranker.pkl` | Model_A_Full | LinearSVC — picks best question (custom articles) |
| `model_b/traditional/vectorizer.pkl` | Model_B | TF-IDF for distractor/hint features |
| `model_b/traditional/distractor_ranker.pkl` | Model_B | Random Forest — ranks 3 distractors |
| `model_b/traditional/hint_scorer.pkl` | Model_B | Logistic Regression — picks 3 hints |
