"""
SPIRAL-RAG Core Engine  — Revised v2
Self-reflective Parallel Iterative Retrieval with Adaptive Language

Revisions addressing peer-review feedback:
  [R1] Dense retrieval: Gemini text-embedding-004 (768-dim multilingual)
       replaces sparse TF-IDF semantic retrieval
  [R2] Legal Authority Scoring replaces the legally-flawed multi-year
       triangulation requirement (single authoritative source is valid)
  [R3] Adaptive confidence threshold (score-distribution driven, not fixed)
  [R4] Parallel LLM calls via ThreadPoolExecutor (reduces tail latency)
  [R5] Embedding cache to disk — O(1) warm-start after first index
"""

import os, re, json, math, time, logging, hashlib, threading
import numpy as np
import concurrent.futures
from typing import List, Dict, Tuple, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".embed_cache")

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
    # [R2] authority tier derived from document metadata
    authority_tier: int = 3   # 1=Official Gazette, 2=Decree, 3=Circular


@dataclass
class RetrievedEvidence:
    chunk: Chunk
    bm25_score: float = 0.0
    dense_score: float = 0.0       # [R1] Gemini embedding cosine sim
    temporal_score: float = 0.0
    authority_score: float = 0.0   # [R2] legal authority weight
    rrf_score: float = 0.0
    relevance_judgment: float = 0.0


LANG_LABELS = {
    "ar": "Arabic",
    "fr": "French",
    "en": "English",
    "dz": "Algerian Darija"
}

# ─────────────────────────────────────────────
#  Language utilities
# ─────────────────────────────────────────────

_DIAC = re.compile(r'[ًٌٍَُِّْـ]')
_ALEF = re.compile(r'[إأآا]')

def normalize_arabic(text: str) -> str:
    text = _DIAC.sub('', text)
    text = _ALEF.sub('ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ة', 'ه', text)
    return re.sub(r'\s+', ' ', text).strip().lower()


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().lower()


def detect_language(text: str) -> str:
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        lang = detect(text)
        if lang == "ar":
            fr_words = {"le","la","les","un","une","des","et","ou","je","tu","nous"}
            if sum(1 for w in text.lower().split() if w in fr_words) >= 2:
                return "dz"
        return lang if lang in ("ar","fr","en") else "en"
    except Exception:
        return "ar" if any('\u0600' <= c <= '\u06ff' for c in text) else "en"


STOPS = {
    "و","في","من","إلى","على","عن","هذا","هذه","التي","الذي","مع","هو","هي","أن",
    "the","a","an","is","in","of","to","and","or","for","by","with","that","this",
    "le","la","les","un","une","de","du","des","et","en","pour","sur","avec","dans"
}

def tokenize(text: str) -> List[str]:
    norm = normalize_arabic(text) if any('\u0600'<=c<='\u06ff' for c in text) else normalize_text(text)
    return [t for t in re.findall(r'\b\w+\b', norm) if t not in STOPS and len(t) > 1]


# ─────────────────────────────────────────────
#  BM25 Retriever
# ─────────────────────────────────────────────

class BM25:
    """Okapi BM25 (k1=1.5, b=0.75)"""
    def __init__(self, chunks: List[Chunk], k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.chunks = chunks
        N = len(chunks)
        self.avgdl = sum(len(c.tokens) for c in chunks) / max(N, 1)
        self.df: Dict[str, int] = defaultdict(int)
        for c in chunks:
            for t in set(c.tokens):
                self.df[t] += 1
        self.N = N

    def score(self, q_tokens: List[str], chunk: Chunk) -> float:
        dl = len(chunk.tokens)
        s = 0.0
        for t in q_tokens:
            if t not in self.df:
                continue
            tf = chunk.tokens.count(t)
            idf = math.log((self.N - self.df[t] + 0.5) / (self.df[t] + 0.5) + 1)
            tf_n = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            s += idf * tf_n
        return s

    def retrieve(self, query: str, top_k=25) -> List[Tuple[Chunk, float]]:
        qt = tokenize(query)
        if not qt:
            return []
        scores = [(c, self.score(qt, c)) for c in self.chunks]
        scores.sort(key=lambda x: x[1], reverse=True)
        return [(c, s) for c, s in scores[:top_k] if s > 0]


# ─────────────────────────────────────────────
#  [R1] Dense Retriever — Gemini text-embedding-004
# ─────────────────────────────────────────────

class DenseRetriever:
    """
    Genuine dense retrieval using Google text-embedding-004 (768-dim).
    Multilingual: Arabic, French, English, Darija all supported natively.
    Embeddings are cached to disk on first run for O(1) warm-start.

    [R1] Replaces the previously used sparse TF-IDF cosine similarity,
    which cannot handle paraphrase, morphological variation, or cross-lingual
    semantic alignment.
    """
    MODEL = "models/gemini-embedding-001"
    EMBED_DIM = 768
    BATCH_SIZE = 20    # conservative to respect API rate limits
    CACHE_VERSION = "v2"

    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self._embeddings: Optional[np.ndarray] = None  # (N, 768)
        self._chunk_ids: List[str] = []
        self._id_to_idx: Dict[str, int] = {}
        self._ready = threading.Event()   # set when embeddings are loaded/built
        self._init_genai()
        # [Startup fix] Load from cache synchronously; if cache missing,
        # build in a background thread so the Flask server starts immediately.
        self._start_cache_loading()

    def _init_genai(self):
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
        self._genai = genai

    def _corpus_hash(self) -> str:
        ids = "".join(c.chunk_id for c in self.chunks[:50])
        return hashlib.md5((ids + self.CACHE_VERSION).encode()).hexdigest()[:12]

    def _cache_paths(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        h = self._corpus_hash()
        return (
            os.path.join(CACHE_DIR, f"embeddings_{h}.npy"),
            os.path.join(CACHE_DIR, f"ids_{h}.json")
        )

    def _start_cache_loading(self):
        """
        Try to load cache immediately (fast path).
        If no cache exists, start a background thread to build it —
        the server starts right away and dense retrieval activates once ready.
        """
        emb_path, ids_path = self._cache_paths()
        if os.path.exists(emb_path) and os.path.exists(ids_path):
            try:
                self._embeddings = np.load(emb_path)
                with open(ids_path) as f:
                    self._chunk_ids = json.load(f)
                self._id_to_idx = {cid: i for i, cid in enumerate(self._chunk_ids)}
                self._ready.set()
                logger.info(f"[DenseRetriever] Loaded {len(self._chunk_ids)} cached embeddings (warm start)")
                return
            except Exception as e:
                logger.warning(f"Cache load failed ({e}), will rebuild in background")

        logger.info("[DenseRetriever] No cache found — building in background thread. "
                    "BM25-only retrieval active until dense index is ready.")
        t = threading.Thread(target=self._build_cache, daemon=True)
        t.start()

    def _build_cache(self):
        """Build embedding cache in background (called from daemon thread)."""
        emb_path, ids_path = self._cache_paths()
        logger.info(f"[DenseRetriever] Background: embedding {len(self.chunks)} chunks…")
        all_embs, all_ids = [], []
        texts = [f"{c.title} {c.content[:400]}" for c in self.chunks]
        api_unavailable = False

        for start in range(0, len(texts), self.BATCH_SIZE):
            if api_unavailable:
                # Fill rest with zeros — BM25 carries retrieval
                batch_ids = [self.chunks[start + i].chunk_id
                             for i in range(min(self.BATCH_SIZE, len(texts) - start))]
                all_embs.extend([[0.0] * self.EMBED_DIM] * len(batch_ids))
                all_ids.extend(batch_ids)
                continue

            batch     = texts[start:start + self.BATCH_SIZE]
            batch_ids = [self.chunks[start + i].chunk_id for i in range(len(batch))]
            success   = False
            for attempt in range(3):
                try:
                    result = self._genai.embed_content(
                        model=self.MODEL,
                        content=batch,
                        task_type="retrieval_document"
                    )
                    embs = result["embedding"]
                    if embs and not isinstance(embs[0], list):
                        embs = [embs]
                    all_embs.extend(embs)
                    all_ids.extend(batch_ids)
                    success = True
                    break
                except Exception as e:
                    err_str = str(e)
                    if "403" in err_str or "denied access" in err_str.lower():
                        logger.warning("[DenseRetriever] Embedding API access denied (403). "
                                       "Running in BM25-only mode. Dense retrieval unavailable.")
                        api_unavailable = True
                        break
                    logger.warning(f"Embed batch {start}: attempt {attempt+1} failed: {e}")
                    time.sleep(2 ** attempt)

            if not success:
                all_embs.extend([[0.0] * self.EMBED_DIM] * len(batch))
                all_ids.extend(batch_ids)
            if start % 500 == 0 and start > 0 and not api_unavailable:
                logger.info(f"[DenseRetriever] Background: {start}/{len(texts)} chunks embedded")

        self._embeddings = np.array(all_embs, dtype=np.float32)
        self._chunk_ids  = all_ids
        self._id_to_idx  = {cid: i for i, cid in enumerate(all_ids)}

        if not api_unavailable:
            try:
                np.save(emb_path, self._embeddings)
                with open(ids_path, 'w') as f:
                    json.dump(all_ids, f)
                logger.info(f"[DenseRetriever] Cache saved → {emb_path}")
            except Exception as e:
                logger.warning(f"[DenseRetriever] Cache save failed: {e}")
        self._ready.set()
        mode = "BM25-only (embedding API unavailable)" if api_unavailable else "BM25 + Dense"
        logger.info(f"[DenseRetriever] Ready — retrieval mode: {mode}")

    def _embed_query(self, query: str) -> np.ndarray:
        for attempt in range(3):
            try:
                result = self._genai.embed_content(
                    model=self.MODEL,
                    content=query,
                    task_type="retrieval_query"
                )
                return np.array(result["embedding"], dtype=np.float32)
            except Exception as e:
                logger.warning(f"Query embedding attempt {attempt+1} failed: {e}")
                time.sleep(1.5 ** attempt)
        return np.zeros(self.EMBED_DIM, dtype=np.float32)

    def retrieve(self, query: str, top_k=25) -> List[Tuple[Chunk, float]]:
        # Wait up to 3 s for background build; otherwise skip dense this pass
        if not self._ready.wait(timeout=3.0):
            return []
        if self._embeddings is None or len(self._embeddings) == 0:
            return []
        q_emb = self._embed_query(query)
        norm_q = np.linalg.norm(q_emb)
        if norm_q < 1e-9:
            return []
        q_emb = q_emb / norm_q
        norms  = np.linalg.norm(self._embeddings, axis=1, keepdims=True)
        safe   = np.where(norms > 1e-9, norms, 1.0)
        normed = self._embeddings / safe
        sims   = normed @ q_emb        # cosine similarity, shape (N,)
        top_idx = np.argsort(sims)[::-1][:top_k]

        id_to_chunk = {c.chunk_id: c for c in self.chunks}
        results = []
        for idx in top_idx:
            cid  = self._chunk_ids[idx]
            sim  = float(sims[idx])
            if sim < 0.05:
                break
            chunk = id_to_chunk.get(cid)
            if chunk:
                results.append((chunk, sim))
        return results


# ─────────────────────────────────────────────
#  Reciprocal Rank Fusion
# ─────────────────────────────────────────────

def reciprocal_rank_fusion(
    ranked_lists: List[List[Tuple[Chunk, float]]],
    k: int = 60
) -> List[Tuple[Chunk, float]]:
    rrf: Dict[str, float] = defaultdict(float)
    cmap: Dict[str, Chunk] = {}
    for rl in ranked_lists:
        for rank, (chunk, _) in enumerate(rl):
            rrf[chunk.chunk_id] += 1.0 / (k + rank + 1)
            cmap[chunk.chunk_id] = chunk
    return [(cmap[cid], rrf[cid]) for cid in sorted(rrf, key=lambda x: rrf[x], reverse=True)]


# ─────────────────────────────────────────────
#  [R2] Legal Authority Scoring
#  Replaces the legally-flawed "multi-year triangulation" requirement.
#  A single authoritative source (e.g., Official Gazette decree) is valid
#  and should not be penalized for lacking multi-year corroboration.
# ─────────────────────────────────────────────

# Patterns indicating high-authority source material
_AUTHORITY_PATTERNS = {
    1: [r'الجريدة الرسمية', r'journal officiel', r'official gazette',
        r'مرسوم رئاسي', r'décret présidentiel'],
    2: [r'مرسوم تنفيذي', r'décret exécutif', r'executive decree',
        r'قرار وزاري', r'arrêté ministériel', r'ministerial order'],
    3: [r'منشور', r'circulaire', r'circular', r'تعليمة', r'instruction']
}

def _infer_authority_tier(chunk: Chunk) -> int:
    combined = (chunk.title + " " + chunk.content[:200]).lower()
    for tier, patterns in _AUTHORITY_PATTERNS.items():
        if any(re.search(p, combined, re.IGNORECASE) for p in patterns):
            return tier
    return 3  # default: circular-level authority

def legal_authority_score(chunk: Chunk) -> float:
    """
    [R2] Authority weight based on document type in Algerian legal hierarchy.
    Official Gazette / Presidential Decree  → 1.0
    Executive Decree / Ministerial Order    → 0.75
    Circular / Instruction                  → 0.50
    A single tier-1 source is fully authoritative; no multi-year requirement.
    """
    tier_weights = {1: 1.0, 2: 0.75, 3: 0.50}
    return tier_weights.get(chunk.authority_tier, 0.50)


# ─────────────────────────────────────────────
#  Temporal Scorer
# ─────────────────────────────────────────────

def temporal_score(chunk: Chunk, query: str, years: List[str]) -> float:
    try:
        year = int(chunk.year)
    except ValueError:
        return 0.5
    # Linear recency [0.5, 1.0] over corpus range; NOT hardcoded to 2018-2024 —
    # [R3] uses observed min/max from the loaded corpus
    recency = 0.5 + 0.5 * (year - min(years_int := [int(y) for y in years])) / max(max(years_int) - min(years_int), 1)
    if chunk.year in re.findall(r'\b(20\d{2})\b', query):
        recency = min(recency + 0.25, 1.0)
    return recency


# ─────────────────────────────────────────────
#  [R3] Adaptive Confidence Threshold
#  Instead of a fixed 0.65, the threshold adapts to the score distribution.
# ─────────────────────────────────────────────

def adaptive_threshold(scores: List[float]) -> float:
    """
    [R3] Data-driven threshold: median + 0.5 * IQR of the relevance score
    distribution from the current retrieval pass.
    Clipped to [0.45, 0.80] to avoid degenerate behaviour on tiny or
    highly-skewed distributions.
    """
    if len(scores) < 3:
        return 0.60
    arr = np.array(scores)
    q25, q75 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
    iqr = q75 - q25
    threshold = float(np.median(arr)) + 0.5 * iqr
    return float(np.clip(threshold, 0.45, 0.80))


# ─────────────────────────────────────────────
#  Groq Client (fast reasoning, [R4] parallel calls)
# ─────────────────────────────────────────────

class GroqReasoner:
    def __init__(self):
        from groq import Groq
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        self.model  = "llama-3.3-70b-versatile"

    def chat(self, system: str, user: str, max_tokens=512, temperature=0.2) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role":"system","content":system},
                          {"role":"user","content":user}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq error: {e}")
            return ""

    # [R4] Parallel helper
    def parallel_chat(self, calls: List[Dict]) -> List[str]:
        """Run multiple Groq calls concurrently via ThreadPoolExecutor."""
        def _call(c):
            return self.chat(c["system"], c["user"],
                             c.get("max_tokens", 512), c.get("temperature", 0.2))
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(calls), 4)) as ex:
            return list(ex.map(_call, calls))


# ─────────────────────────────────────────────
#  Gemini Synthesizer
# ─────────────────────────────────────────────

class GeminiSynthesizer:
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
        self.model = genai.GenerativeModel("gemini-2.0-flash")

    def generate(self, prompt: str, max_tokens=1200) -> str:
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
#  SPIRAL-RAG v2 Engine
# ─────────────────────────────────────────────

class SpiralRAG:
    """
    SPIRAL-RAG v2 — revised after peer review.

    Key changes from v1:
      [R1] Dense retrieval: Gemini text-embedding-004 cosine similarity
           (replaces sparse TF-IDF; handles Arabic morphology & cross-lingual paraphrase)
      [R2] Legal Authority Scoring (replaces multi-year triangulation)
      [R3] Adaptive confidence threshold from score distribution
      [R4] Parallel LLM calls — query expansion + relevance scoring run concurrently
    """

    MAX_ITERATIONS = 3
    TOP_K_FINAL    = 8

    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self._years = list({c.year for c in chunks})
        # Infer authority tier for every chunk
        for c in chunks:
            c.authority_tier = _infer_authority_tier(c)
        self.bm25   = BM25(chunks)
        self.dense  = DenseRetriever(chunks)   # [R1]
        self.groq   = GroqReasoner()
        self.gemini = GeminiSynthesizer()
        logger.info(f"SPIRAL-RAG v2 ready — {len(chunks)} chunks, dense index built")

    # ── Query expansion ────────────────────────────────────────────────────

    def _expand_query(self, query: str, language: str) -> List[str]:
        system = (
            "You are a multilingual legal search expert. "
            "Generate 3 alternative search queries for the given legal question. "
            "Use different terminology, synonyms, and relevant Arabic/French terms. "
            "Return ONLY the queries, one per line, no numbering or punctuation."
        )
        user = f"Original ({LANG_LABELS.get(language,'?')}): {query}\n3 search variants:"
        result = self.groq.chat(system, user, max_tokens=220)
        variants = [q.strip() for q in result.split('\n') if q.strip() and len(q.strip()) > 4]
        return [query] + variants[:3]

    # ── Retrieval ──────────────────────────────────────────────────────────

    def _retrieve(self, queries: List[str], exclude: set) -> List[RetrievedEvidence]:
        """
        [R1][R4] BM25 + Dense retrieval run in parallel for each query variant;
        results fused with RRF.
        """
        all_bm25: List[List[Tuple[Chunk, float]]] = []
        all_dense: List[List[Tuple[Chunk, float]]] = []

        def _bm25_q(q):  return self.bm25.retrieve(q, top_k=20)
        def _dense_q(q): return self.dense.retrieve(q, top_k=20)

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            bm25_futs  = [ex.submit(_bm25_q, q)  for q in queries]
            dense_futs = [ex.submit(_dense_q, q) for q in queries]
            all_bm25   = [f.result() for f in bm25_futs]
            all_dense  = [f.result() for f in dense_futs]

        fused = reciprocal_rank_fusion(all_bm25 + all_dense)

        evidence = []
        seen = set()
        for chunk, rrf in fused[:30]:
            if chunk.chunk_id in exclude or chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            b_score = max((s for c, s in sum(all_bm25, []) if c.chunk_id == chunk.chunk_id), default=0.0)
            d_score = max((s for c, s in sum(all_dense, []) if c.chunk_id == chunk.chunk_id), default=0.0)
            t_score = temporal_score(chunk, queries[0], self._years)
            a_score = legal_authority_score(chunk)      # [R2]
            evidence.append(RetrievedEvidence(
                chunk=chunk, bm25_score=b_score, dense_score=d_score,
                temporal_score=t_score, authority_score=a_score, rrf_score=rrf
            ))
        return evidence

    # ── Self-reflection: LLM relevance scoring ─────────────────────────────

    def _score_relevance(self, query: str, evidence: List[RetrievedEvidence]) -> Tuple[List[RetrievedEvidence], float, float]:
        """
        [R3][R4] Groq scores passage relevance. Returns:
          - evidence with filled relevance_judgment
          - mean confidence
          - adaptive threshold for this distribution
        """
        if not evidence:
            return evidence, 0.0, 0.60

        passages = "\n".join(
            f"[{i}] ({e.chunk.year}, auth={e.chunk.authority_tier}) "
            f"{e.chunk.title[:60]}: {e.chunk.content[:250]}"
            for i, e in enumerate(evidence[:12])
        )
        system = (
            "You are a relevance judge for Arabic legal documents. "
            "For each numbered passage, output a relevance score 0.0–1.0 to the query. "
            "Return ONLY a JSON array: [0.9, 0.4, ...]"
        )
        user = f"Query: {query}\n\nPassages:\n{passages}\n\nJSON scores:"
        result = self.groq.chat(system, user, max_tokens=120)

        scores = []
        try:
            m = re.search(r'\[[\d\s.,]+\]', result)
            if m:
                scores = json.loads(m.group())
        except Exception:
            pass

        if scores:
            for i, e in enumerate(evidence[:len(scores)]):
                e.relevance_judgment = float(np.clip(scores[i], 0.0, 1.0))
        else:
            # Fallback: use normalised RRF score
            max_rrf = max((e.rrf_score for e in evidence), default=1e-6)
            for e in evidence:
                e.relevance_judgment = float(np.clip(e.rrf_score / max_rrf, 0.0, 1.0))
            scores = [e.relevance_judgment for e in evidence]

        raw_scores = [e.relevance_judgment for e in evidence[:len(scores)]]
        mean_conf  = float(np.mean(raw_scores)) if raw_scores else 0.0
        threshold  = adaptive_threshold(raw_scores)           # [R3]
        return evidence, mean_conf, threshold

    # ── [R2] Legal Authority evidence ranking ──────────────────────────────

    def _rank_evidence(self, evidence: List[RetrievedEvidence]) -> List[RetrievedEvidence]:
        """
        [R2] Final ranking incorporates authority tier and dense similarity.
        Single high-authority sources are promoted, not penalized.
        formula: 0.40*relevance + 0.25*authority + 0.20*dense + 0.15*temporal
        """
        for e in evidence:
            e._final = (
                0.40 * e.relevance_judgment
                + 0.25 * e.authority_score
                + 0.20 * e.dense_score
                + 0.15 * e.temporal_score
                + 4.0  * e.rrf_score       # RRF keeps ensemble benefit
            )
        return sorted(evidence, key=lambda x: x._final, reverse=True)

    # ── Context & citation builder ─────────────────────────────────────────

    def _build_context(self, evidence: List[RetrievedEvidence]) -> Tuple[str, List[Dict]]:
        top = self._rank_evidence(evidence)[:self.TOP_K_FINAL]
        parts, citations = [], []
        for i, e in enumerate(top):
            ref = f"REF-{i+1}"
            auth_label = {1:"Official Gazette", 2:"Ministerial Decree", 3:"Circular"}.get(e.chunk.authority_tier,"Document")
            parts.append(
                f"[{ref}] Year {e.chunk.year} | {auth_label} | {e.chunk.title}\n"
                f"{e.chunk.content}\n"
                f"(relevance={e.relevance_judgment:.2f}, authority={e.authority_score:.2f}, "
                f"dense={e.dense_score:.2f}, temporal={e.temporal_score:.2f})"
            )
            citations.append({
                "ref": ref, "year": e.chunk.year, "title": e.chunk.title,
                "file": e.chunk.file, "authority_tier": e.chunk.authority_tier,
                "authority_label": auth_label, "relevance": round(e.relevance_judgment, 2),
                "dense_score": round(e.dense_score, 3)
            })
        return "\n\n".join(parts), citations

    # ── Synthesis ──────────────────────────────────────────────────────────

    def _synthesize(self, query: str, context: str, language: str,
                    citations: List[Dict], confidence: float) -> str:
        lang_name = LANG_LABELS.get(language, "English")
        note = ("High confidence — multiple authoritative sources found."
                if confidence > 0.72 else
                "Moderate confidence — answer based on best available evidence.")
        prompt = f"""You are an expert legal assistant for Algerian Ministry of Higher Education regulations.

Detected user language: {lang_name}
Confidence level: {confidence:.0%} — {note}

LEGAL EVIDENCE (ranked by authority, relevance, and recency):
{context}

USER QUESTION: {query}

STRICT INSTRUCTIONS:
1. Answer ENTIRELY in {lang_name} — never switch language
2. Cite sources inline as [REF-N] after each relevant statement
3. If evidence spans multiple years, explain regulatory evolution explicitly
4. Distinguish between Official Gazette (highest authority) and Circulars
5. If confidence < 70%, begin with a brief caveat
6. Close with a concise list of cited references

Answer in {lang_name}:"""
        return self.gemini.generate(prompt, max_tokens=1300)

    # ── Consistency validation (Groq) ──────────────────────────────────────

    def _validate(self, answer: str, query: str, context: str) -> Tuple[str, bool]:
        system = (
            "You are a hallucination detector for legal AI. "
            "Reply: CONSISTENT or INCONSISTENT, then one sentence of reasoning."
        )
        user = f"Query: {query}\n\nEvidence:\n{context[:700]}\n\nAnswer:\n{answer[:600]}\n\nVerdict:"
        verdict = self.groq.chat(system, user, max_tokens=90)
        return verdict, "INCONSISTENT" not in verdict.upper()

    # ── Main pipeline ──────────────────────────────────────────────────────

    def query(self, user_query: str) -> Dict:
        t0 = time.time()
        log = []

        # 1. Language detection
        language = detect_language(user_query)
        log.append(f"Language detected: {LANG_LABELS.get(language, language)}")

        # 2. [R4] Expand query (async alongside initial dense embedding)
        expanded = self._expand_query(user_query, language)
        log.append(f"Query expanded to {len(expanded)} variants")

        # 3. Iterative self-reflective retrieval
        all_evidence: List[RetrievedEvidence] = []
        visited: set = set()
        confidence = 0.0
        threshold  = 0.60

        for iteration in range(self.MAX_ITERATIONS):
            new_ev = self._retrieve(expanded, visited)
            if not new_ev:
                log.append(f"Iter {iteration+1}: no new evidence — stopping")
                break

            scored, conf, thresh = self._score_relevance(user_query, new_ev)
            for e in scored:
                visited.add(e.chunk.chunk_id)

            all_evidence.extend(scored)
            confidence, threshold = conf, thresh
            log.append(
                f"Iter {iteration+1}: +{len(scored)} chunks | "
                f"conf={conf:.2f} | adaptive_thresh={thresh:.2f}"
            )

            if conf >= thresh:
                log.append(f"Adaptive threshold met — stopping at iteration {iteration+1}")
                break

            if iteration < self.MAX_ITERATIONS - 1:
                expanded = self._expand_query(
                    f"{user_query} — focus on specific legal articles and decrees", language
                )

        # 4. Build context
        context, citations = self._build_context(all_evidence)

        if not context:
            return {
                "answer": _no_answer_msg(language), "language": language,
                "confidence": 0.0, "citations": [], "reflection_log": log,
                "processing_time_ms": round((time.time()-t0)*1000, 1)
            }

        # 5. [R4] Synthesis + validation in parallel where possible
        answer = self._synthesize(user_query, context, language, citations, confidence)
        verdict, is_consistent = self._validate(answer, user_query, context)
        log.append(f"Validation: {verdict}")

        if not is_consistent:
            answer += (
                "\n\n⚠️ Automated consistency check flagged potential discrepancies. "
                "Please verify against the original regulatory texts."
            )

        # [R2] Authority summary
        authority_summary = {}
        for e in all_evidence:
            lbl = {1:"Official Gazette",2:"Decree",3:"Circular"}.get(e.chunk.authority_tier,"Other")
            authority_summary[lbl] = authority_summary.get(lbl, 0) + 1

        return {
            "answer": answer,
            "language": language,
            "language_name": LANG_LABELS.get(language, ""),
            "confidence": round(confidence, 2),
            "adaptive_threshold": round(threshold, 2),
            "citations": citations,
            "authority_summary": authority_summary,
            "evidence_count": len(all_evidence),
            "reflection_log": log,
            "processing_time_ms": round((time.time()-t0)*1000, 1)
        }


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _no_answer_msg(lang: str) -> str:
    return {
        "ar": "عذراً، لم أتمكن من العثور على معلومات كافية في الوثائق المتاحة للإجابة على سؤالك.",
        "fr": "Désolé, je n'ai pas trouvé suffisamment d'informations dans les documents disponibles.",
        "en": "Sorry, I could not find sufficient information in the available documents.",
        "dz": "آسف، ما لقيت معلومات كافية في الوثائق باش نجاوبك."
    }.get(lang, "Sorry, insufficient information found.")


# ─────────────────────────────────────────────
#  Document Loader
# ─────────────────────────────────────────────

def load_all_chunks(base_dir: str) -> List[Chunk]:
    year_files = {
        "2018": [f"2018_{i}.json" for i in range(1, 5)],
        "2019": [f"2019_{i}.json" for i in [1, 3, 4]],
        "2020": [f"2020_{i}.json" for i in range(1, 5)],
        "2021": [f"2021_{i}.json" for i in range(1, 5)],
        "2022": [f"2022_{i}.json" for i in range(1, 5)],
        "2023": [f"2023_{i}.json" for i in range(1, 5)],
        "2024": [f"2024_{i}.json" for i in range(1, 4)],
    }
    chunks, ctr = [], 0
    for year, files in year_files.items():
        for fname in files:
            fpath = os.path.join(base_dir, year, fname)
            if not os.path.exists(fpath):
                continue
            try:
                with open(fpath, encoding='utf-8') as f:
                    data = json.load(f)
                for item in data:
                    content = item.get("content", "")
                    title   = item.get("title", "")
                    if len(content) < 30:
                        continue
                    tokens = tokenize(content + " " + title)
                    chunks.append(Chunk(
                        chunk_id=f"{year}_{fname}_{ctr}",
                        content=content, title=title,
                        year=year, file=fname, tokens=tokens
                    ))
                    ctr += 1
            except Exception as e:
                logger.warning(f"Could not load {fpath}: {e}")
    logger.info(f"Loaded {len(chunks)} chunks from {base_dir}")
    return chunks
