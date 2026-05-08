"""
SPIRAL-RAG Core Engine
Self-reflective Parallel Iterative Retrieval with Adaptive Language

Novel Architecture:
  - Dual-LLM: Groq (fast, reasoning) + Gemini (synthesis)
  - Iterative self-reflective retrieval with confidence scoring
  - Cross-lingual BM25 + semantic ensemble via RRF
  - Temporal evidence weighting
  - Evidence triangulation with citation tracing
  - Adaptive context window selection
"""

import os
import re
import json
import math
import time
import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Data Structures
# ─────────────────────────────────────────────

@dataclass
class Chunk:
    chunk_id: str
    content: str
    title: str
    year: str
    file: str
    tokens: List[str] = field(default_factory=list)

@dataclass
class RetrievedEvidence:
    chunk: Chunk
    bm25_score: float = 0.0
    semantic_score: float = 0.0
    temporal_score: float = 0.0
    rrf_score: float = 0.0
    relevance_judgment: float = 0.0  # LLM-scored relevance


@dataclass
class SpiralState:
    query: str
    language: str
    canonical_query: str
    expanded_queries: List[str]
    retrieved: List[RetrievedEvidence]
    visited_ids: set
    iteration: int
    confidence: float
    final_answer: str
    citations: List[Dict]
    reflection_log: List[str]


# ─────────────────────────────────────────────
#  Language Utilities
# ─────────────────────────────────────────────

LANG_LABELS = {
    "ar": "Arabic",
    "fr": "French",
    "en": "English",
    "dz": "Algerian Darija"
}

ARABIC_DIACRITICS = re.compile(r'[ًٌٍَُِّْـ]')
ARABIC_ALEF = re.compile(r'[إأآا]')


def normalize_arabic(text: str) -> str:
    text = ARABIC_DIACRITICS.sub('', text)
    text = ARABIC_ALEF.sub('ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()


def normalize_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()


def detect_language(text: str) -> str:
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        lang = detect(text)
        # Darija heuristic: detected as Arabic but has French/Spanish words
        if lang == "ar":
            french_words = ["le", "la", "les", "un", "une", "des", "et", "ou", "je", "tu", "nous"]
            words = text.lower().split()
            if sum(1 for w in words if w in french_words) >= 2:
                return "dz"
        return lang if lang in ["ar", "fr", "en"] else "en"
    except Exception:
        return "ar" if any('\u0600' <= c <= '\u06ff' for c in text) else "en"


def tokenize(text: str) -> List[str]:
    normalized = normalize_arabic(text) if any('\u0600' <= c <= '\u06ff' for c in text) else normalize_text(text)
    tokens = re.findall(r'\b\w+\b', normalized)
    # Remove short stopwords
    stops = {
        "و", "في", "من", "إلى", "على", "عن", "هذا", "هذه", "التي", "الذي", "مع",
        "the", "a", "an", "is", "in", "of", "to", "and", "or", "for", "by",
        "le", "la", "les", "un", "une", "de", "du", "des", "et", "en"
    }
    return [t for t in tokens if t not in stops and len(t) > 1]


# ─────────────────────────────────────────────
#  BM25 Retriever
# ─────────────────────────────────────────────

class BM25:
    """Okapi BM25 with k1=1.5, b=0.75"""

    def __init__(self, chunks: List[Chunk], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks = chunks
        self.N = len(chunks)
        self.avgdl = sum(len(c.tokens) for c in chunks) / max(self.N, 1)
        self.df: Dict[str, int] = defaultdict(int)
        for c in chunks:
            for term in set(c.tokens):
                self.df[term] += 1

    def score(self, query_tokens: List[str], chunk: Chunk) -> float:
        score = 0.0
        dl = len(chunk.tokens)
        for term in query_tokens:
            if term not in self.df:
                continue
            tf = chunk.tokens.count(term)
            idf = math.log((self.N - self.df[term] + 0.5) / (self.df[term] + 0.5) + 1)
            tf_norm = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            score += idf * tf_norm
        return score

    def retrieve(self, query: str, top_k: int = 20) -> List[Tuple[Chunk, float]]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = [(c, self.score(q_tokens, c)) for c in self.chunks]
        scores.sort(key=lambda x: x[1], reverse=True)
        return [(c, s) for c, s in scores[:top_k] if s > 0]


# ─────────────────────────────────────────────
#  Semantic Retriever (TF-IDF cosine similarity)
# ─────────────────────────────────────────────

class SemanticRetriever:
    """Fast TF-IDF cosine similarity for semantic matching."""

    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self.N = len(chunks)
        # Build IDF
        self.df: Dict[str, int] = defaultdict(int)
        for c in chunks:
            for term in set(c.tokens):
                self.df[term] += 1
        self.idf: Dict[str, float] = {
            t: math.log((self.N + 1) / (df + 1)) + 1
            for t, df in self.df.items()
        }
        # Precompute TF-IDF vectors
        self.vectors = [self._vectorize(c.tokens) for c in chunks]

    def _vectorize(self, tokens: List[str]) -> Dict[str, float]:
        tf = Counter(tokens)
        total = max(sum(tf.values()), 1)
        return {t: (tf[t] / total) * self.idf.get(t, 1.0) for t in tf}

    def _cosine(self, v1: Dict[str, float], v2: Dict[str, float]) -> float:
        common = set(v1) & set(v2)
        if not common:
            return 0.0
        dot = sum(v1[t] * v2[t] for t in common)
        norm1 = math.sqrt(sum(x * x for x in v1.values()))
        norm2 = math.sqrt(sum(x * x for x in v2.values()))
        return dot / (norm1 * norm2 + 1e-9)

    def retrieve(self, query: str, top_k: int = 20) -> List[Tuple[Chunk, float]]:
        q_tokens = tokenize(query)
        q_vec = self._vectorize(q_tokens)
        if not q_vec:
            return []
        scores = [(self.chunks[i], self._cosine(q_vec, self.vectors[i]))
                  for i in range(self.N)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return [(c, s) for c, s in scores[:top_k] if s > 0.01]


# ─────────────────────────────────────────────
#  Reciprocal Rank Fusion
# ─────────────────────────────────────────────

def reciprocal_rank_fusion(
    ranked_lists: List[List[Tuple[Chunk, float]]],
    k: int = 60
) -> List[Tuple[Chunk, float]]:
    """Combine multiple ranked lists using RRF."""
    rrf_scores: Dict[str, float] = defaultdict(float)
    chunk_map: Dict[str, Chunk] = {}
    for ranked in ranked_lists:
        for rank, (chunk, _) in enumerate(ranked):
            rrf_scores[chunk.chunk_id] += 1.0 / (k + rank + 1)
            chunk_map[chunk.chunk_id] = chunk
    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
    return [(chunk_map[cid], rrf_scores[cid]) for cid in sorted_ids]


# ─────────────────────────────────────────────
#  Temporal Scorer
# ─────────────────────────────────────────────

def temporal_score(chunk: Chunk, query: str, base_year: int = 2018) -> float:
    """Score chunks higher if they are more recent OR if query mentions their year."""
    try:
        year = int(chunk.year)
    except ValueError:
        return 0.5
    # Recency boost: 2018 → 0.5, 2024 → 1.0
    recency = 0.5 + 0.5 * (year - base_year) / max(2024 - base_year, 1)
    # Query year match
    years_in_query = re.findall(r'\b(201[89]|202[0-4])\b', query)
    if years_in_query and chunk.year in years_in_query:
        recency = min(recency + 0.3, 1.0)
    return recency


# ─────────────────────────────────────────────
#  Groq Client (fast reasoning)
# ─────────────────────────────────────────────

class GroqReasoner:
    def __init__(self):
        from groq import Groq
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        self.model = "llama-3.3-70b-versatile"

    def chat(self, system: str, user: str, max_tokens: int = 512, temperature: float = 0.2) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq error: {e}")
            return ""


# ─────────────────────────────────────────────
#  Gemini Client (synthesis)
# ─────────────────────────────────────────────

class GeminiSynthesizer:
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        try:
            resp = self.model.generate_content(
                prompt,
                generation_config={"max_output_tokens": max_tokens, "temperature": 0.3}
            )
            return resp.text.strip()
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return ""


# ─────────────────────────────────────────────
#  SPIRAL-RAG Engine
# ─────────────────────────────────────────────

class SpiralRAG:
    """
    Self-reflective Parallel Iterative Retrieval with Adaptive Language
    
    Pipeline:
      1. Language detection & cross-lingual query normalization (Groq)
      2. Parallel BM25 + Semantic retrieval → RRF ensemble
      3. Self-reflection loop: LLM scores relevance → re-queries if needed
      4. Temporal evidence weighting & re-ranking
      5. Evidence triangulation (multi-source corroboration)
      6. Adaptive synthesis in user's language (Gemini)
      7. Citation chain construction
    """

    MAX_ITERATIONS = 3
    CONFIDENCE_THRESHOLD = 0.65
    TOP_K_FINAL = 8

    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self.bm25 = BM25(chunks)
        self.semantic = SemanticRetriever(chunks)
        self.groq = GroqReasoner()
        self.gemini = GeminiSynthesizer()
        logger.info(f"SPIRAL-RAG initialized with {len(chunks)} chunks")

    def _expand_query(self, query: str, language: str) -> List[str]:
        """Use Groq to generate search query variants."""
        lang_name = LANG_LABELS.get(language, "English")
        system = (
            "You are a multilingual legal search assistant. "
            "Generate 3 alternative search queries for the given question. "
            "Each variant should use different terminology or perspective. "
            "Also include an Arabic version if the input is not Arabic. "
            "Return ONLY the queries, one per line, no numbering."
        )
        user = f"Original question ({lang_name}): {query}\nGenerate 3 search variants:"
        result = self.groq.chat(system, user, max_tokens=200)
        variants = [q.strip() for q in result.split('\n') if q.strip() and len(q.strip()) > 5]
        return [query] + variants[:3]

    def _retrieve_for_query(self, query: str, exclude_ids: set) -> List[RetrievedEvidence]:
        """Run BM25 + semantic retrieval and fuse via RRF."""
        bm25_results = self.bm25.retrieve(query, top_k=15)
        sem_results = self.semantic.retrieve(query, top_k=15)

        fused = reciprocal_rank_fusion([bm25_results, sem_results])

        evidence = []
        for chunk, rrf in fused[:20]:
            if chunk.chunk_id in exclude_ids:
                continue
            # Find individual scores
            bm25_s = next((s for c, s in bm25_results if c.chunk_id == chunk.chunk_id), 0.0)
            sem_s = next((s for c, s in sem_results if c.chunk_id == chunk.chunk_id), 0.0)
            t_score = temporal_score(chunk, query)
            evidence.append(RetrievedEvidence(
                chunk=chunk,
                bm25_score=bm25_s,
                semantic_score=sem_s,
                temporal_score=t_score,
                rrf_score=rrf
            ))
        return evidence

    def _score_relevance(self, query: str, evidence: List[RetrievedEvidence]) -> Tuple[List[RetrievedEvidence], float]:
        """Groq scores relevance of each retrieved passage (self-reflection step)."""
        if not evidence:
            return evidence, 0.0

        passages = "\n".join([
            f"[{i}] (Year {e.chunk.year}) {e.chunk.title}: {e.chunk.content[:300]}"
            for i, e in enumerate(evidence[:10])
        ])

        system = (
            "You are a relevance judge for legal documents. "
            "Score each passage's relevance to the query from 0.0 to 1.0. "
            "Return ONLY a JSON array of numbers like: [0.9, 0.3, 0.7, ...]"
        )
        user = f"Query: {query}\n\nPassages:\n{passages}\n\nReturn relevance scores as JSON array:"
        result = self.groq.chat(system, user, max_tokens=100)

        try:
            match = re.search(r'\[[\d\s.,]+\]', result)
            if match:
                scores = json.loads(match.group())
                for i, e in enumerate(evidence[:len(scores)]):
                    e.relevance_judgment = float(scores[i])
                avg_confidence = sum(scores[:len(evidence)]) / max(len(evidence), 1)
                return evidence, min(avg_confidence, 1.0)
        except Exception:
            pass

        # Fallback: use RRF score as proxy
        for e in evidence:
            e.relevance_judgment = min(e.rrf_score * 10, 1.0)
        avg = sum(e.relevance_judgment for e in evidence) / max(len(evidence), 1)
        return evidence, avg

    def _triangulate_evidence(self, evidence: List[RetrievedEvidence]) -> Dict[str, List[RetrievedEvidence]]:
        """Group evidence by year-source for triangulation."""
        groups: Dict[str, List[RetrievedEvidence]] = defaultdict(list)
        for e in evidence:
            groups[e.chunk.year].append(e)
        return groups

    def _build_context(self, evidence: List[RetrievedEvidence]) -> Tuple[str, List[Dict]]:
        """Build context string and citation list from top evidence."""
        top = sorted(evidence, key=lambda x: x.relevance_judgment * 0.5 + x.rrf_score * 5 + x.temporal_score * 0.3, reverse=True)
        top = top[:self.TOP_K_FINAL]

        context_parts = []
        citations = []
        for i, e in enumerate(top):
            ref_num = i + 1
            context_parts.append(
                f"[REF-{ref_num}] Year {e.chunk.year} | {e.chunk.title}\n"
                f"{e.chunk.content}\n"
                f"(Relevance: {e.relevance_judgment:.2f}, Temporal: {e.temporal_score:.2f})"
            )
            citations.append({
                "ref": f"REF-{ref_num}",
                "year": e.chunk.year,
                "title": e.chunk.title,
                "file": e.chunk.file,
                "relevance": round(e.relevance_judgment, 2)
            })
        return "\n\n".join(context_parts), citations

    def _synthesize(self, query: str, context: str, language: str, citations: List[Dict], confidence: float) -> str:
        """Use Gemini to synthesize the final answer with citations."""
        lang_name = LANG_LABELS.get(language, "English")
        triangulated_note = "High confidence answer (multiple corroborating sources)" if confidence > 0.75 else "Moderate confidence — answer based on available evidence"

        prompt = f"""You are an expert legal assistant for Algerian Ministry of Higher Education regulations.

User's language: {lang_name}
Query confidence level: {confidence:.0%} — {triangulated_note}

RETRIEVED LEGAL EVIDENCE:
{context}

USER QUESTION: {query}

INSTRUCTIONS:
1. Answer ENTIRELY in {lang_name} — this is mandatory
2. Structure your answer clearly with sections if the answer is complex
3. Cite your sources using [REF-N] notation inline
4. If evidence is from multiple years, highlight any differences or evolution of the regulation
5. If confidence is below 70%, add a note that the answer may be incomplete
6. Be precise and legally accurate — avoid speculation
7. At the end, list cited references briefly

Answer in {lang_name}:"""

        return self.gemini.generate(prompt, max_tokens=1200)

    def _validate_answer(self, answer: str, query: str, context: str) -> Tuple[str, bool]:
        """Groq validates consistency of the generated answer with evidence."""
        system = (
            "You are a fact-checker for legal AI systems. "
            "Check if the answer is consistent with the provided evidence. "
            "Reply with: CONSISTENT or INCONSISTENT, followed by a one-line reason."
        )
        user = f"Query: {query}\n\nEvidence summary:\n{context[:800]}\n\nGenerated answer:\n{answer[:600]}\n\nVerdict:"
        verdict = self.groq.chat(system, user, max_tokens=80)
        is_consistent = "INCONSISTENT" not in verdict.upper()
        return verdict, is_consistent

    def query(self, user_query: str) -> Dict:
        """Main SPIRAL-RAG pipeline."""
        start_time = time.time()
        reflection_log = []

        # Step 1: Language detection
        language = detect_language(user_query)
        reflection_log.append(f"Detected language: {LANG_LABELS.get(language, language)}")

        # Step 2: Query expansion via Groq
        expanded_queries = self._expand_query(user_query, language)
        reflection_log.append(f"Expanded to {len(expanded_queries)} query variants")

        # Step 3: Iterative self-reflective retrieval
        all_evidence: List[RetrievedEvidence] = []
        visited_ids: set = set()
        confidence = 0.0

        for iteration in range(self.MAX_ITERATIONS):
            iteration_evidence = []
            for q in expanded_queries:
                retrieved = self._retrieve_for_query(q, visited_ids)
                iteration_evidence.extend(retrieved)

            # Deduplicate
            seen = set()
            unique_evidence = []
            for e in iteration_evidence:
                if e.chunk.chunk_id not in seen:
                    seen.add(e.chunk.chunk_id)
                    unique_evidence.append(e)
                    visited_ids.add(e.chunk.chunk_id)

            if not unique_evidence:
                reflection_log.append(f"Iteration {iteration+1}: No new evidence found, stopping")
                break

            # Self-reflection: LLM scores relevance
            scored_evidence, iteration_confidence = self._score_relevance(user_query, unique_evidence)
            all_evidence.extend(scored_evidence)
            confidence = iteration_confidence

            reflection_log.append(
                f"Iteration {iteration+1}: Retrieved {len(unique_evidence)} chunks, "
                f"confidence={confidence:.2f}"
            )

            if confidence >= self.CONFIDENCE_THRESHOLD:
                reflection_log.append(f"Confidence threshold met — stopping at iteration {iteration+1}")
                break

            if iteration < self.MAX_ITERATIONS - 1:
                # Re-expand with feedback
                low_rel = [e for e in scored_evidence if e.relevance_judgment < 0.4]
                if low_rel:
                    reflection_log.append(f"Low-relevance passages found — refining query")
                    expanded_queries = self._expand_query(
                        f"{user_query} (more specific, legal regulation context)", language
                    )

        # Step 4: Build context with temporal weighting
        context, citations = self._build_context(all_evidence)

        if not context:
            return {
                "answer": _no_answer_msg(language),
                "language": language,
                "confidence": 0.0,
                "citations": [],
                "iterations": 1,
                "reflection_log": reflection_log,
                "processing_time_ms": (time.time() - start_time) * 1000
            }

        # Step 5: Synthesize answer (Gemini)
        answer = self._synthesize(user_query, context, language, citations, confidence)

        # Step 6: Validate consistency (Groq)
        verdict, is_consistent = self._validate_answer(answer, user_query, context)
        reflection_log.append(f"Validation: {verdict}")

        if not is_consistent:
            answer += "\n\n⚠️ Note: Some parts of this answer could not be fully verified against available sources."

        # Step 7: Evidence triangulation summary
        source_groups = self._triangulate_evidence(all_evidence)
        corroborated_years = [yr for yr, evs in source_groups.items() if len(evs) >= 2]

        processing_time = (time.time() - start_time) * 1000
        return {
            "answer": answer,
            "language": language,
            "confidence": round(confidence, 2),
            "citations": citations,
            "corroborated_by_years": corroborated_years,
            "iterations": len(reflection_log),
            "reflection_log": reflection_log,
            "evidence_count": len(all_evidence),
            "processing_time_ms": round(processing_time, 1)
        }


def _no_answer_msg(lang: str) -> str:
    msgs = {
        "ar": "عذراً، لم أتمكن من العثور على معلومات كافية للإجابة على سؤالك في الوثائق المتاحة.",
        "fr": "Désolé, je n'ai pas trouvé suffisamment d'informations pour répondre à votre question dans les documents disponibles.",
        "en": "Sorry, I couldn't find sufficient information to answer your question in the available documents.",
        "dz": "آسف، ما لقيت معلومات كافية باش نجاوبك على سؤالك في الوثائق المتاحة."
    }
    return msgs.get(lang, msgs["en"])


# ─────────────────────────────────────────────
#  Document Loader
# ─────────────────────────────────────────────

def load_all_chunks(base_dir: str) -> List[Chunk]:
    """Load all JSON documents from year subdirectories."""
    year_to_files = {
        "2018": [f"2018_{i}.json" for i in range(1, 5)],
        "2019": [f"2019_{i}.json" for i in [1, 3, 4]],
        "2020": [f"2020_{i}.json" for i in range(1, 5)],
        "2021": [f"2021_{i}.json" for i in range(1, 5)],
        "2022": [f"2022_{i}.json" for i in range(1, 5)],
        "2023": [f"2023_{i}.json" for i in range(1, 5)],
        "2024": [f"2024_{i}.json" for i in range(1, 4)],
    }

    all_chunks: List[Chunk] = []
    chunk_counter = 0

    for year, files in year_to_files.items():
        for fname in files:
            fpath = os.path.join(base_dir, year, fname)
            if not os.path.exists(fpath):
                continue
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for item in data:
                    content = item.get("content", "")
                    title = item.get("title", "")
                    if len(content) < 30:
                        continue
                    cid = f"{year}_{fname}_{chunk_counter}"
                    tokens = tokenize(content + " " + title)
                    all_chunks.append(Chunk(
                        chunk_id=cid,
                        content=content,
                        title=title,
                        year=year,
                        file=fname,
                        tokens=tokens
                    ))
                    chunk_counter += 1
            except Exception as e:
                logger.warning(f"Could not load {fpath}: {e}")

    logger.info(f"Loaded {len(all_chunks)} chunks from {base_dir}")
    return all_chunks
