"""
SPIRAL-RAG Evaluation Benchmark Generator
Generates 300+ evaluation questions across 4 languages and 6 question types.
Outputs a CSV ready for human annotation + automated RAGAS evaluation.

Usage:
    python evaluation/generate_benchmark.py --output evaluation/benchmark.csv

Question types:
  1. Factual     — direct article lookup
  2. Temporal    — year-specific rule query
  3. Comparative — how did a rule change between years?
  4. Procedural  — step-by-step process
  5. Eligibility — yes/no eligibility criteria
  6. Darija      — Algerian dialect questions (dedicated subset)
"""

import os, sys, json, csv, re, random
from typing import List, Dict
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Rag'))
from rag_core import load_all_chunks, Chunk

BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'Rag')
OUTPUT   = os.path.join(os.path.dirname(__file__), 'benchmark.csv')

random.seed(42)

# ─────────────────────────────────────────────
#  Question templates per type and language
# ─────────────────────────────────────────────

TEMPLATES = {
    "factual": {
        "ar": [
            "ما هي شروط {topic}؟",
            "كيف يتم تحديد {topic} وفق اللوائح المعمول بها؟",
            "ما هي المتطلبات القانونية لـ{topic}؟",
            "ما الذي تنص عليه التعليمات الوزارية بشأن {topic}؟",
        ],
        "fr": [
            "Quelles sont les conditions relatives à {topic}?",
            "Comment est défini {topic} selon la réglementation en vigueur?",
            "Quelles sont les exigences légales concernant {topic}?",
            "Que stipulent les instructions ministérielles sur {topic}?",
        ],
        "en": [
            "What are the requirements for {topic}?",
            "How is {topic} defined under current regulations?",
            "What do ministerial instructions say about {topic}?",
            "What are the legal conditions governing {topic}?",
        ],
    },
    "temporal": {
        "ar": [
            "ما كانت شروط {topic} في سنة {year}؟",
            "كيف كانت تُطبَّق أحكام {topic} خلال {year}؟",
            "ما اللوائح المتعلقة بـ{topic} الصادرة عام {year}؟",
        ],
        "fr": [
            "Quelles étaient les conditions de {topic} en {year}?",
            "Comment les dispositions relatives à {topic} étaient-elles appliquées en {year}?",
            "Quels textes réglementaires sur {topic} ont été publiés en {year}?",
        ],
        "en": [
            "What were the requirements for {topic} in {year}?",
            "How were regulations on {topic} applied during {year}?",
            "What regulatory texts on {topic} were issued in {year}?",
        ],
    },
    "comparative": {
        "ar": [
            "كيف تغيرت شروط {topic} بين {year1} و{year2}؟",
            "ما الفرق بين لوائح {topic} في {year1} مقارنةً بـ{year2}؟",
        ],
        "fr": [
            "Comment les conditions de {topic} ont-elles évolué entre {year1} et {year2}?",
            "Quelle est la différence entre la réglementation de {topic} en {year1} et {year2}?",
        ],
        "en": [
            "How did the requirements for {topic} change between {year1} and {year2}?",
            "What is the difference between regulations on {topic} in {year1} vs {year2}?",
        ],
    },
    "procedural": {
        "ar": [
            "ما هي إجراءات التقدم لـ{topic}؟",
            "كيف تتم عملية {topic} خطوة بخطوة؟",
            "ما الوثائق المطلوبة لـ{topic}؟",
        ],
        "fr": [
            "Quelle est la procédure pour {topic}?",
            "Comment se déroule le processus de {topic} étape par étape?",
            "Quels documents sont requis pour {topic}?",
        ],
        "en": [
            "What is the procedure for {topic}?",
            "What are the step-by-step steps for {topic}?",
            "What documents are required for {topic}?",
        ],
    },
    "eligibility": {
        "ar": [
            "من يحق له الاستفادة من {topic}؟",
            "ما شروط الأهلية للحصول على {topic}؟",
            "هل يحق للطالب الأجنبي الاستفادة من {topic}؟",
        ],
        "fr": [
            "Qui est éligible à {topic}?",
            "Quelles sont les conditions d'éligibilité pour {topic}?",
            "Un étudiant étranger peut-il bénéficier de {topic}?",
        ],
        "en": [
            "Who is eligible for {topic}?",
            "What are the eligibility criteria for {topic}?",
            "Can a foreign student benefit from {topic}?",
        ],
    },
    "darija": {
        "dz": [
            "واش هي شروط {topic}؟",
            "كيفاش تتقدم لـ{topic} في الجامعة؟",
            "من يقدر يستافد من {topic}؟",
            "شكون يخدم على {topic}؟",
            "واش لازم نجيب من وثائق باش نسجل في {topic}؟",
        ],
    },
}

TOPICS = [
    # Arabic topics
    ("التسجيل في الدكتوراه", "doctoral enrollment"),
    ("المنحة الوطنية للتميز", "excellence national scholarship"),
    ("التكوين في اللغة العربية", "Arabic language training"),
    ("التدرج في الرتب الأكاديمية", "academic rank promotion"),
    ("الاعتراف بشهادة أجنبية", "foreign diploma recognition"),
    ("الانتقال بين الجامعات", "inter-university transfer"),
    ("اللجنة الوطنية للتعليم العالي", "national higher education committee"),
    ("التكوين عن بعد", "distance learning"),
    ("شهادة الليسانس", "bachelor's degree"),
    ("شهادة الماستر", "master's degree"),
    ("التفرغ العلمي", "research leave"),
    ("الترسيم في الطور الأول", "first cycle registration"),
    ("منحة الإقامة", "residence scholarship"),
    ("التعاون الدولي في التعليم", "international academic cooperation"),
    ("البحث العلمي للطلبة", "student scientific research"),
    ("التكوين ما بعد التدرج", "postgraduate training"),
    ("الترخيص بفتح مؤسسة خاصة", "private institution licensing"),
    ("إعادة التوجيه", "academic reorientation"),
    ("منحة التفوق", "merit scholarship"),
    ("الإجازة الاستثنائية للأستاذ", "professor exceptional leave"),
]

YEARS = ["2018", "2019", "2020", "2021", "2022", "2023", "2024"]


def extract_topics_from_corpus(chunks: List[Chunk], n=30) -> List[str]:
    """Extract high-frequency meaningful titles from the corpus."""
    title_counts: Dict[str, int] = {}
    for c in chunks:
        t = c.title.strip()
        if 10 < len(t) < 120:
            title_counts[t] = title_counts.get(t, 0) + 1
    sorted_titles = sorted(title_counts, key=lambda x: title_counts[x], reverse=True)
    return sorted_titles[:n]


def generate_questions(corpus_topics: List[str]) -> List[Dict]:
    rows = []
    q_id = 1

    all_topics = [(t, t) for t in corpus_topics] + TOPICS

    # ── Factual (4 langs × ~20 topics = 80 questions)
    for topic_ar, topic_en in random.sample(all_topics, min(20, len(all_topics))):
        for lang in ("ar", "fr", "en"):
            tmpl = random.choice(TEMPLATES["factual"][lang])
            topic = topic_ar if lang == "ar" else topic_en
            rows.append({
                "id": f"Q{q_id:04d}", "type": "factual", "language": lang,
                "question": tmpl.format(topic=topic),
                "expected_years": "",
                "ground_truth_answer": "",
                "human_rating": "",
                "notes": f"topic_ref={topic_en}"
            })
            q_id += 1

    # ── Temporal (3 langs × 3 templates × 7 years × sampled topics = ~63)
    for year in YEARS:
        for topic_ar, topic_en in random.sample(all_topics, min(3, len(all_topics))):
            for lang in ("ar", "fr", "en"):
                tmpl = random.choice(TEMPLATES["temporal"][lang])
                topic = topic_ar if lang == "ar" else topic_en
                rows.append({
                    "id": f"Q{q_id:04d}", "type": "temporal", "language": lang,
                    "question": tmpl.format(topic=topic, year=year),
                    "expected_years": year,
                    "ground_truth_answer": "",
                    "human_rating": "",
                    "notes": f"year={year}, topic_ref={topic_en}"
                })
                q_id += 1

    # ── Comparative (2 langs × 7 year-pairs × 3 topics = 42)
    year_pairs = [("2018","2020"),("2019","2022"),("2020","2023"),
                  ("2021","2024"),("2018","2024"),("2019","2021"),("2022","2024")]
    for y1, y2 in year_pairs:
        for topic_ar, topic_en in random.sample(all_topics, min(3, len(all_topics))):
            for lang in ("ar", "fr", "en"):
                tmpl = random.choice(TEMPLATES["comparative"][lang])
                topic = topic_ar if lang == "ar" else topic_en
                rows.append({
                    "id": f"Q{q_id:04d}", "type": "comparative", "language": lang,
                    "question": tmpl.format(topic=topic, year1=y1, year2=y2),
                    "expected_years": f"{y1},{y2}",
                    "ground_truth_answer": "",
                    "human_rating": "",
                    "notes": f"years={y1}-{y2}, topic_ref={topic_en}"
                })
                q_id += 1

    # ── Procedural (3 langs × 15 topics = 45)
    for topic_ar, topic_en in random.sample(all_topics, min(15, len(all_topics))):
        for lang in ("ar", "fr", "en"):
            tmpl = random.choice(TEMPLATES["procedural"][lang])
            topic = topic_ar if lang == "ar" else topic_en
            rows.append({
                "id": f"Q{q_id:04d}", "type": "procedural", "language": lang,
                "question": tmpl.format(topic=topic),
                "expected_years": "",
                "ground_truth_answer": "",
                "human_rating": "",
                "notes": f"topic_ref={topic_en}"
            })
            q_id += 1

    # ── Eligibility (3 langs × 10 topics = 30)
    for topic_ar, topic_en in random.sample(all_topics, min(10, len(all_topics))):
        for lang in ("ar", "fr", "en"):
            tmpl = random.choice(TEMPLATES["eligibility"][lang])
            topic = topic_ar if lang == "ar" else topic_en
            rows.append({
                "id": f"Q{q_id:04d}", "type": "eligibility", "language": lang,
                "question": tmpl.format(topic=topic),
                "expected_years": "",
                "ground_truth_answer": "",
                "human_rating": "",
                "notes": f"topic_ref={topic_en}"
            })
            q_id += 1

    # ── Darija dedicated subset (5 templates × 10 topics = 50)
    for topic_ar, topic_en in random.sample(all_topics, min(10, len(all_topics))):
        for tmpl in TEMPLATES["darija"]["dz"]:
            rows.append({
                "id": f"Q{q_id:04d}", "type": "darija", "language": "dz",
                "question": tmpl.format(topic=topic_ar),
                "expected_years": "",
                "ground_truth_answer": "",
                "human_rating": "",
                "notes": f"darija_subset, topic_ref={topic_en}"
            })
            q_id += 1

    random.shuffle(rows)
    # Re-assign IDs after shuffle
    for i, r in enumerate(rows):
        r["id"] = f"Q{i+1:04d}"

    return rows


def write_csv(rows: List[Dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = ["id","type","language","question","expected_years",
              "ground_truth_answer","human_rating","notes"]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {len(rows)} questions to {path}")

    # Stats
    from collections import Counter
    type_counts = Counter(r["type"] for r in rows)
    lang_counts = Counter(r["language"] for r in rows)
    print("\nBreakdown by type:")
    for t, n in sorted(type_counts.items()):
        print(f"  {t:15s}: {n}")
    print("\nBreakdown by language:")
    for l, n in sorted(lang_counts.items()):
        print(f"  {l:5s}: {n}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()

    print("Loading corpus to extract topics…")
    chunks = load_all_chunks(BASE_DIR)
    corpus_topics = extract_topics_from_corpus(chunks, n=30)
    print(f"Extracted {len(corpus_topics)} high-frequency topics from corpus")

    rows = generate_questions(corpus_topics)
    write_csv(rows, args.output)
