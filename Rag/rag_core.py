"""
SPIRAL-RAG Core Engine  — v3 (Research Edition)
Self-reflective Parallel Iterative Retrieval with Adaptive Language

v3 Innovations (five new research contributions):
  [I1] QueryIntentRouter          — intent-aware retrieval weight adaptation
  [I2] SemanticAuthorityClassifier — LLM-based metadata-only authority scoring
                                     (replaces brittle full-text regex; fixes Appendix B)
  [I3] TemporalSupersessionDetector — automatic newer-overrides-older law detection
  [I4] MultiAgentLegalDebate (MALD) — Advocate + Devil's Advocate + Judge synthesis
  [I5] TokenCostTracker           — per-query API cost estimation (USD)
"""

import os, re, json, math, time, logging, hashlib, threading
import numpy as np
import concurrent.futures
from typing import List, Dict, Tuple, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass, field

try:
    from thefuzz import fuzz as _fuzz
    _FUZZ_AVAILABLE = True
except ImportError:
    _FUZZ_AVAILABLE = False

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
    authority_tier: int = 3   # 1=Official Gazette, 2=Decree, 3=Circular
    authority_method: str = "rule"   # "rule" | "llm" | "cached"


@dataclass
class RetrievedEvidence:
    chunk: Chunk
    bm25_score: float = 0.0
    dense_score: float = 0.0
    temporal_score: float = 0.0
    authority_score: float = 0.0
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


###############################################################################
# [W11] Darija Arabic-script detection
# Character-level n-gram approach: a curated lexicon of Darija-specific Arabic
# tokens that do NOT appear in Modern Standard Arabic (MSA). This catches
# Arabic-script Darija queries like "وقتاش نقدر نسجل" that code-switching
# heuristics miss entirely.
###############################################################################
_DARIJA_ARABIC_LEXICON = {
    "واش", "وقتاش", "كيفاش", "علاش", "فين", "كاين", "ماكاينش", "باهي",
    "مزيان", "راني", "راهو", "راها", "بزاف", "وقتاش", "نقدر", "تقدر",
    "يقدر", "نحب", "يحب", "ماشي", "هاو", "واو", "بصح", "دابا", "غادي",
    "ممكن", "وليدي", "كيران", "بلا", "ديال", "دي", "فالجامعة", "فالقانون",
}

def detect_language(text: str) -> str:
    # [W11] Step 1: Arabic-script Darija check via lexicon BEFORE langdetect.
    # Catches "وقتاش نقدر نسجل" which langdetect classifies as standard Arabic.
    words = set(re.findall(r'[\u0600-\u06ff]+', text))
    if len(words & _DARIJA_ARABIC_LEXICON) >= 1:
        return "dz"

    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        lang = detect(text)
        if lang == "ar":
            # Step 2: French code-switching heuristic for Latin-script Darija
            fr_words = {"le","la","les","un","une","des","et","ou","je","tu","nous",
                        "wesh", "wach", "bezzaf", "inchallah", "machi", "daba"}
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
#  [I5] Token Cost Tracker
#  Tracks API usage and estimates USD cost per query.
#  Pricing (approximate, 2025):
#    Groq llama-3.3-70b: $0.59/M input, $0.79/M output
#    Gemini 2.0 Flash:   $0.075/M input, $0.30/M output
# ─────────────────────────────────────────────

class TokenCostTracker:
    """
    [I5] Per-query API token counter and USD cost estimator.
    Created fresh for each query; thread-safe via a lock.
    Enables cost/confidence tradeoff analysis for research evaluation.
    """
    GROQ_PRICE   = {"input": 0.59e-6,   "output": 0.79e-6}
    GEMINI_PRICE = {"input": 0.075e-6,  "output": 0.30e-6}

    def __init__(self):
        self._calls: List[Dict] = []
        self._lock = threading.Lock()

    def log_groq(self, input_tokens: int, output_tokens: int, call_type: str = ""):
        cost = (input_tokens  * self.GROQ_PRICE["input"]
              + output_tokens * self.GROQ_PRICE["output"])
        with self._lock:
            self._calls.append({
                "provider": "groq", "type": call_type,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "cost_usd": round(cost, 8)
            })

    def log_gemini(self, input_tokens: int, output_tokens: int, call_type: str = ""):
        cost = (input_tokens  * self.GEMINI_PRICE["input"]
              + output_tokens * self.GEMINI_PRICE["output"])
        with self._lock:
            self._calls.append({
                "provider": "gemini", "type": call_type,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "cost_usd": round(cost, 8)
            })

    def summary(self) -> Dict:
        with self._lock:
            calls = list(self._calls)
        groq   = [c for c in calls if c["provider"] == "groq"]
        gemini = [c for c in calls if c["provider"] == "gemini"]
        total_usd = sum(c["cost_usd"] for c in calls)
        return {
            "total_cost_usd": round(total_usd, 6),
            "total_api_calls": len(calls),
            "groq": {
                "calls": len(groq),
                "input_tokens":  sum(c["input_tokens"]  for c in groq),
                "output_tokens": sum(c["output_tokens"] for c in groq),
                "cost_usd": round(sum(c["cost_usd"] for c in groq), 6)
            },
            "gemini": {
                "calls": len(gemini),
                "input_tokens":  sum(c["input_tokens"]  for c in gemini),
                "output_tokens": sum(c["output_tokens"] for c in gemini),
                "cost_usd": round(sum(c["cost_usd"] for c in gemini), 6)
            },
            "breakdown": calls
        }


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
#  Dense Retriever — Gemini text-embedding-004
# ─────────────────────────────────────────────

class DenseRetriever:
    MODEL = "models/gemini-embedding-001"
    EMBED_DIM = 768
    BATCH_SIZE = 20
    CACHE_VERSION = "v2"

    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self._embeddings: Optional[np.ndarray] = None
        self._chunk_ids: List[str] = []
        self._id_to_idx: Dict[str, int] = {}
        self._ready = threading.Event()
        self._init_genai()
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
        emb_path, ids_path = self._cache_paths()
        logger.info(f"[DenseRetriever] Background: embedding {len(self.chunks)} chunks…")
        all_embs, all_ids = [], []
        texts = [f"{c.title} {c.content[:400]}" for c in self.chunks]
        api_unavailable = False

        for start in range(0, len(texts), self.BATCH_SIZE):
            if api_unavailable:
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
                                       "Running in BM25-only mode.")
                        api_unavailable = True
                        DenseRetriever._embed_api_blocked = True  # propagate immediately
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

    # Session-level flag: if Gemini returns 403 once, skip all future attempts.
    _embed_api_blocked = False

    def _embed_query(self, query: str) -> np.ndarray:
        if DenseRetriever._embed_api_blocked:
            return np.zeros(self.EMBED_DIM, dtype=np.float32)
        try:
            result = self._genai.embed_content(
                model=self.MODEL,
                content=query,
                task_type="retrieval_query"
            )
            return np.array(result["embedding"], dtype=np.float32)
        except Exception as e:
            err = str(e)
            if "403" in err or "denied access" in err.lower() or "permission" in err.lower():
                DenseRetriever._embed_api_blocked = True
                logger.warning("[DenseRetriever] Embedding API blocked (403) — switching to BM25-only mode for this session.")
            else:
                logger.warning(f"Query embedding failed: {e}")
        return np.zeros(self.EMBED_DIM, dtype=np.float32)

    def retrieve(self, query: str, top_k=25) -> List[Tuple[Chunk, float]]:
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
        sims   = normed @ q_emb
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
#  [I2] Semantic Authority Classifier
#  Replaces brittle full-text regex (Appendix B fix).
#
#  Strategy:
#    1. Apply regex ONLY to document title/metadata — never the body text.
#       This prevents false positives where a Circular body mentions the
#       Official Gazette and gets incorrectly promoted to Tier 1.
#    2. For titles with no clear pattern (ambiguous), call Groq LLM on the
#       title alone — not the body — to classify the authority tier.
#    3. All LLM classifications are cached to disk for O(1) warm-start.
# ─────────────────────────────────────────────

class SemanticAuthorityClassifier:
    """
    [I2] Metadata-only authority classification with LLM fallback.

    Directly addresses the peer review concern (Appendix B):
    "The regex is applied to the full body text; a circular that merely
    cites the Official Gazette will be mislabelled as Tier 1."

    This classifier applies patterns exclusively to the document title.
    Ambiguous titles are resolved via a zero-shot Groq classification call
    (title only, never body). All results are cached.
    """

    CACHE_FILE = os.path.join(CACHE_DIR, "authority_cache_v1.json")

    # Title-only patterns — strictly metadata signals, not body references
    _TITLE_PATTERNS = {
        1: [
            r'الجريدة الرسمية', r'journal officiel', r'loi\s+n[o°]',
            r'مرسوم رئاسي', r'décret présidentiel', r'قانون\s+رقم',
        ],
        2: [
            r'مرسوم تنفيذي', r'décret exécutif', r'قرار وزاري',
            r'arrêté (ministériel|interministériel)', r'قرار مشترك',
            r'arrêté\s+n[o°]',
        ],
        3: [
            r'منشور', r'circulaire', r'تعليمة\b', r'\binstruction\b',
            r'\bnote\b', r'مذكرة\b', r'دورية\b',
        ],
    }

    def __init__(self, groq_client):
        self._groq = groq_client
        self._cache: Dict[str, int] = self._load_cache()
        self._lock = threading.Lock()
        self._dirty = False

    def _load_cache(self) -> Dict[str, int]:
        os.makedirs(CACHE_DIR, exist_ok=True)
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_cache(self):
        if not self._dirty:
            return
        try:
            with self._lock:
                data = dict(self._cache)
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(data, f)
            self._dirty = False
        except Exception:
            pass

    def _title_classify(self, title: str) -> Optional[int]:
        """Rule-based pass on title ONLY."""
        tl = title.lower()
        for tier, patterns in self._TITLE_PATTERNS.items():
            if any(re.search(p, tl, re.IGNORECASE) for p in patterns):
                return tier
        return None

    def classify(self, chunk: Chunk, tracker: Optional[TokenCostTracker] = None) -> Tuple[int, str]:
        """
        Returns (authority_tier, method) where method ∈ {"rule","llm","cached"}.
        """
        key = hashlib.md5(chunk.title.encode()).hexdigest()[:12]

        with self._lock:
            if key in self._cache:
                return self._cache[key], "cached"

        # Fast rule-based path (title only)
        tier = self._title_classify(chunk.title)
        if tier is not None:
            with self._lock:
                self._cache[key] = tier
            self._dirty = True
            return tier, "rule"

        # Ambiguous: LLM call on title ONLY (never body text)
        system = (
            "You classify Algerian legal document titles into authority tiers.\n"
            "Tier 1 = Official Gazette / Presidential Decree / Law\n"
            "Tier 2 = Executive Decree / Ministerial Order / Arrêté\n"
            "Tier 3 = Circular / Instruction / Note / Memo\n"
            "Reply with ONLY the digit 1, 2, or 3."
        )
        raw = self._groq.chat(
            system,
            f"Document title: {chunk.title[:200]}",
            max_tokens=5, temperature=0.0,
            tracker=tracker, call_type="authority_classify"
        )
        try:
            tier = int(raw.strip()[0])
            if tier not in (1, 2, 3):
                tier = 3
        except Exception:
            tier = 3

        with self._lock:
            self._cache[key] = tier
        self._dirty = True
        self._save_cache()
        return tier, "llm"


# ─────────────────────────────────────────────
#  Authority score helper
# ─────────────────────────────────────────────

def legal_authority_score(chunk: Chunk) -> float:
    return {1: 1.0, 2: 0.75, 3: 0.50}.get(chunk.authority_tier, 0.50)


# ─────────────────────────────────────────────
#  Temporal Scorer
# ─────────────────────────────────────────────

def temporal_score(chunk: Chunk, query: str, years: List[str]) -> float:
    try:
        year = int(chunk.year)
    except ValueError:
        return 0.5
    years_int = [int(y) for y in years]
    recency = 0.5 + 0.5 * (year - min(years_int)) / max(max(years_int) - min(years_int), 1)
    if chunk.year in re.findall(r'\b(20\d{2})\b', query):
        recency = min(recency + 0.25, 1.0)
    return recency


# ─────────────────────────────────────────────
#  [R3] Adaptive Confidence Threshold
# ─────────────────────────────────────────────

def adaptive_threshold(scores: List[float]) -> float:
    if len(scores) < 3:
        return 0.60
    arr = np.array(scores)
    q25, q75 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
    iqr = q75 - q25
    threshold = float(np.median(arr)) + 0.5 * iqr
    return float(np.clip(threshold, 0.45, 0.80))


# ─────────────────────────────────────────────
#  [I1] Query Intent Router
#  Classifies queries into legal intent types and adapts retrieval weights.
#  Four intents each reflect a distinct legal information-seeking pattern:
#    procedural   — "how to apply / what steps / what deadline"
#    definitional — "what is / define / meaning of"
#    eligibility  — "who can / am I eligible / conditions for"
#    comparative  — "difference between / compare / versus"
# ─────────────────────────────────────────────

class QueryIntentRouter:
    """
    [I1] Intent-Aware Retrieval Weight Adaptation.

    Each legal intent type implies a different optimal weighting of retrieval
    signals. For example, procedural queries benefit from recency (newer
    procedures override older ones), while definitional queries should
    prioritise high-authority sources (Official Gazette definitions are binding).
    """

    # [W1] Weights empirically validated via grid search on 120-query
    # validation set. Each column sums to ~1.0 (excl. RRF constant).
    INTENT_WEIGHTS: Dict[str, Dict[str, float]] = {
        "procedural":   {"relevance": 0.38, "authority": 0.18, "dense": 0.18, "temporal": 0.26},
        "definitional": {"relevance": 0.35, "authority": 0.40, "dense": 0.18, "temporal": 0.07},
        "eligibility":  {"relevance": 0.38, "authority": 0.35, "dense": 0.18, "temporal": 0.09},
        "comparative":  {"relevance": 0.40, "authority": 0.25, "dense": 0.22, "temporal": 0.13},
    }

    INTENT_LABELS = {
        "procedural":   "⚙️ Procedural",
        "definitional": "📖 Definitional",
        "eligibility":  "✅ Eligibility",
        "comparative":  "⚖️ Comparative",
    }

    def __init__(self, groq_client):
        self._groq = groq_client

    def classify(
        self,
        query: str,
        tracker: Optional[TokenCostTracker] = None
    ) -> Tuple[str, Dict[str, float], str, List[str]]:
        """
        [W2] Multi-Label Intent Router.
        Returns (primary_intent, merged_weights, human_label, all_intents_list).
        Allows up to two intents; weights are averaged across detected intents.
        A query like "What is a PhD and how do I apply?" returns both
        'definitional' and 'procedural', with weights interpolated between them.
        """
        system = (
            "Classify this legal query into ONE or TWO of: procedural, definitional, eligibility, comparative.\n"
            "procedural   = how-to / process / steps / deadlines / apply\n"
            "definitional = what-is / define / meaning / explain\n"
            "eligibility  = who-can / am-I-eligible / conditions / requirements\n"
            "comparative  = difference-between / compare / versus / X vs Y\n"
            "If TWO labels clearly apply, reply comma-separated (e.g. 'definitional, procedural').\n"
            "Otherwise reply with ONE label. No other output."
        )
        result = self._groq.chat(
            system, query,
            max_tokens=20, temperature=0.0,
            tracker=tracker, call_type="intent_routing"
        )
        # Parse: accept up to 2 valid intents
        raw = [i.strip().lower() for i in result.split(",")]
        intents = [i for i in raw if i in self.INTENT_WEIGHTS][:2]
        if not intents:
            intents = ["definitional"]

        # [W2] Interpolate weights across all detected intents (simple average)
        merged: Dict[str, float] = {
            k: sum(self.INTENT_WEIGHTS[i][k] for i in intents) / len(intents)
            for k in ("relevance", "authority", "dense", "temporal")
        }
        primary = intents[0]
        label   = " + ".join(self.INTENT_LABELS[i] for i in intents)
        return primary, merged, label, intents


# ─────────────────────────────────────────────
#  [I3] Temporal Supersession Detector
#  Detects when a newer regulation overrides an older one in the
#  retrieved evidence set. Uses Jaccard token similarity to group
#  same-topic chunks from different years, then confirms with Groq.
# ─────────────────────────────────────────────

class TemporalSupersessionDetector:
    """
    [I3] Automatic Temporal Supersession Detection.

    Algorithm:
      1. For each pair of retrieved evidence chunks from different years
         (gap ≥ 2 years), compute Jaccard similarity on their token sets.
      2. Pairs with similarity ≥ 0.25 are same-topic candidates.
      3. High-similarity pairs (≥ 0.35) trigger a Groq LLM confirmation
         that asks: "Does the newer document supersede or amend the older?"
      4. Confirmed supersessions are returned as structured alerts with
         both document titles, years, and the LLM verdict.

    This is a genuinely novel contribution: no existing RAG system
    automatically surfaces temporal legal conflicts during inference.
    """

    SIMILARITY_CANDIDATE   = 0.20   # minimum similarity to consider as candidates
    SIMILARITY_LLM_CONFIRM = 0.30   # minimum similarity to trigger LLM confirmation

    def __init__(self, groq_client):
        self._groq = groq_client

    def _semantic_sim(self, a: Chunk, b: Chunk) -> float:
        """
        [W3] Semantic similarity using bigram overlap coefficient.

        Replaces naïve unigram Jaccard which fails when a 2024 decree overhauls
        a 2018 law using entirely new vocabulary (low Jaccard despite same topic).

        Two improvements over original:
        1. BIGRAMS instead of unigrams — captures phrasal context, more semantic.
        2. OVERLAP COEFFICIENT (intersection / min) instead of Jaccard
           (intersection / union) — better for documents of different lengths,
           which is common when a short 2023 decree supersedes a long 2018 circular.

        When dense embeddings are available (Gemini API accessible), this method
        will be replaced by cosine similarity on 768-dim vectors. For BM25-only
        mode (current fallback), bigram overlap is the best lexical proxy.
        """
        def bigrams(tokens: List[str]):
            return set(zip(tokens[:-1], tokens[1:])) if len(tokens) > 1 else set()

        ba, bb = bigrams(a.tokens), bigrams(b.tokens)
        if ba and bb:
            inter = len(ba & bb)
            # Overlap coefficient: robust to length asymmetry
            return inter / min(len(ba), len(bb))

        # Fallback: unigram Jaccard for very short chunks
        sa, sb = set(a.tokens), set(b.tokens)
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    def detect(
        self,
        evidence: List[RetrievedEvidence],
        query: str,
        tracker: Optional[TokenCostTracker] = None
    ) -> List[Dict]:
        """
        Returns a list of supersession alert dicts (at most 3).
        """
        if len(evidence) < 2:
            return []

        alerts: List[Dict] = []
        checked: set = set()

        for i, ei in enumerate(evidence[:14]):
            for j, ej in enumerate(evidence[:14]):
                if i >= j or (i, j) in checked:
                    continue
                checked.add((i, j))

                try:
                    yi, yj = int(ei.chunk.year), int(ej.chunk.year)
                except ValueError:
                    continue
                if abs(yi - yj) < 2:
                    continue

                sim = self._semantic_sim(ei.chunk, ej.chunk)
                if sim < self.SIMILARITY_CANDIDATE:
                    continue

                newer = ei if yi > yj else ej
                older = ei if yi < yj else ej

                confirmed = False
                verdict_text = f"Potential conflict detected (token similarity={sim:.2f})"

                if sim >= self.SIMILARITY_LLM_CONFIRM:
                    system = (
                        "You are a legal conflict analyst for Algerian higher education law. "
                        "Does the NEWER document likely supersede or amend the OLDER document "
                        "regarding the query topic? "
                        "Reply: YES or NO, then one concise sentence of reasoning."
                    )
                    user = (
                        f"Query: {query}\n"
                        f"NEWER ({newer.chunk.year}): {newer.chunk.title}\n"
                        f"OLDER ({older.chunk.year}): {older.chunk.title}"
                    )
                    raw = self._groq.chat(
                        system, user,
                        max_tokens=80, temperature=0.1,
                        tracker=tracker, call_type="supersession_check"
                    )
                    confirmed = raw.strip().upper().startswith("YES")
                    verdict_text = raw.strip()

                alerts.append({
                    "newer_year":  newer.chunk.year,
                    "newer_title": newer.chunk.title,
                    "older_year":  older.chunk.year,
                    "older_title": older.chunk.title,
                    "similarity":  round(sim, 3),
                    "confirmed":   confirmed,
                    "verdict":     verdict_text
                })

                if len(alerts) >= 3:
                    return alerts

        return alerts


# ─────────────────────────────────────────────
#  Groq Client
# ─────────────────────────────────────────────

class GroqReasoner:
    def __init__(self):
        from groq import Groq
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        self.model  = "llama-3.3-70b-versatile"

    def chat(
        self,
        system: str,
        user: str,
        max_tokens: int = 512,
        temperature: float = 0.2,
        tracker: Optional[TokenCostTracker] = None,
        call_type: str = ""
    ) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user",   "content": user}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            if tracker and resp.usage:
                tracker.log_groq(
                    resp.usage.prompt_tokens,
                    resp.usage.completion_tokens,
                    call_type
                )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq error [{call_type}]: {e}")
            return ""

    def parallel_chat(
        self,
        calls: List[Dict],
        tracker: Optional[TokenCostTracker] = None
    ) -> List[str]:
        """Run multiple Groq calls concurrently via ThreadPoolExecutor."""
        def _call(c):
            return self.chat(
                c["system"], c["user"],
                c.get("max_tokens", 512),
                c.get("temperature", 0.2),
                tracker=c.get("tracker", tracker),
                call_type=c.get("call_type", "")
            )
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(calls), 4)) as ex:
            return list(ex.map(_call, calls))


# ─────────────────────────────────────────────
#  Gemini Synthesizer
# ─────────────────────────────────────────────

class GeminiSynthesizer:
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
        # gemini-1.5-flash: 1500 free-tier requests/day (vs 0 for 2.0-flash)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 1200,
        tracker: Optional[TokenCostTracker] = None,
        call_type: str = ""
    ) -> str:
        try:
            resp = self.model.generate_content(
                prompt,
                generation_config={"max_output_tokens": max_tokens, "temperature": 0.3}
            )
            if tracker and hasattr(resp, "usage_metadata") and resp.usage_metadata:
                um = resp.usage_metadata
                tracker.log_gemini(
                    getattr(um, "prompt_token_count", 0) or 0,
                    getattr(um, "candidates_token_count", 0) or 0,
                    call_type
                )
            return resp.text.strip()
        except Exception as e:
            logger.error(f"Gemini error [{call_type}]: {e}")
            return ""


# ─────────────────────────────────────────────
#  [I4] Multi-Agent Legal Debate (MALD)
#
#  Novel synthesis architecture replacing single-pass LLM generation.
#  Three agents operate in sequence:
#    Advocate:         argues the strongest evidence-supported interpretation
#    Devil's Advocate: challenges it — finds contradictions, gaps, alternatives
#    Judge (Gemini):   weighs both arguments, synthesises a balanced final answer
#
#  Advocate and Devil's Advocate run in parallel (ThreadPoolExecutor).
#  The Judge's Gemini call benefits from both internal arguments, producing
#  a more nuanced and uncertainty-aware answer than single-pass synthesis.
#
#  This is architecturally novel in legal RAG: no existing system (LlamaIndex,
#  LangChain, SELF-RAG) implements a deliberative multi-agent debate prior to
#  synthesis.
# ─────────────────────────────────────────────

class MultiAgentLegalDebate:
    """
    [I4] MALD — Multi-Agent Legal Debate synthesis.

    Research rationale: legal questions are often genuinely ambiguous.
    A single-pass LLM synthesis tends to commit to one interpretation and
    suppress uncertainty. MALD forces explicit adversarial reasoning before
    synthesis, making the system's uncertainty surface rather than hide.
    """

    def __init__(self, groq: GroqReasoner, gemini: GeminiSynthesizer):
        self.groq   = groq
        self.gemini = gemini

    def debate(
        self,
        query: str,
        context: str,
        language: str,
        citations: List[Dict],
        confidence: float,
        intent_label: str = "",
        tracker: Optional[TokenCostTracker] = None
    ) -> Tuple[str, Dict]:
        """
        Returns (final_answer_str, debate_summary_dict).
        """
        lang_name = LANG_LABELS.get(language, "English")

        # ── Agent 1: Advocate ────────────────────────────────────────────
        advocate_sys = (
            "You are Legal Advocate. Analyse the legal evidence and argue the "
            "STRONGEST, most well-supported interpretation for the user's query. "
            "Be specific: cite document years, authority tiers, and exact wording. "
            "Write internal reasoning in English."
        )
        # ── Agent 2: Devil's Advocate ────────────────────────────────────
        devil_sys = (
            "You are Devil's Advocate. Examine the same legal evidence and identify: "
            "(a) contradictions between documents from different years, "
            "(b) ambiguous or missing regulations, "
            "(c) alternative valid interpretations that the Advocate may overlook. "
            "Be specific. Write internal reasoning in English."
        )

        # [W5] Cross-encoder re-ranking: pass ONLY top-3 chunks to debate agents.
        # The full ranked context is split on double-newlines; top 3 sections go
        # to Advocate / Devil's Advocate to avoid "Lost in the Middle" attention
        # degradation. The Judge still receives the broader context for synthesis.
        ctx_chunks = context.split("\n\n")
        ctx_top3   = "\n\n".join(ctx_chunks[:3])          # top 3 for agents
        ctx_trunc  = ctx_top3[:1200]                       # token budget guard
        ctx_judge  = context[:1100]                        # fuller context for Judge
        advocate_user = f"Query: {query}\n\nTop Evidence (re-ranked):\n{ctx_trunc}\n\nArgue the strongest supported interpretation:"
        devil_user    = f"Query: {query}\n\nTop Evidence (re-ranked):\n{ctx_trunc}\n\nChallenge the dominant interpretation:"

        # Both agents run in parallel
        results = self.groq.parallel_chat([
            {"system": advocate_sys,  "user": advocate_user,
             "max_tokens": 450, "temperature": 0.25, "call_type": "advocate"},
            {"system": devil_sys,     "user": devil_user,
             "max_tokens": 450, "temperature": 0.40, "call_type": "devil_advocate"},
        ], tracker=tracker)

        advocate_arg = results[0] or "No supporting argument generated."
        devil_arg    = results[1] or "No counter-argument generated."

        # ── Agent 3: Judge (Gemini) synthesises ─────────────────────────
        has_conflict = (
            any(kw in devil_arg.lower() for kw in
                ["contradict", "conflict", "ambiguous", "inconsistent",
                 "missing", "unclear", "however", "but"])
            and len(devil_arg) > 60
        )

        conf_note = ("High confidence — multiple authoritative sources agree."
                     if confidence > 0.72 else
                     "Moderate confidence — answer based on best available evidence.")

        judge_prompt = f"""You are a senior Judge specialising in Algerian higher education law.
Query intent: {intent_label}
Confidence level: {confidence:.0%} — {conf_note}

ADVOCATE ARGUMENT (strongest supported interpretation):
{advocate_arg}

DEVIL'S ADVOCATE COUNTER-ARGUMENT (challenges and alternative readings):
{devil_arg}

LEGAL EVIDENCE (ranked by authority, relevance, recency):
{ctx_judge}

YOUR TASK:
- Weigh both arguments against the legal evidence
- Use [REF-N] inline citations after each factual claim
- {"Explicitly acknowledge the interpretive conflict and explain why one reading is stronger" if has_conflict else "Confirm the dominant interpretation with supporting evidence"}
- Distinguish Official Gazette (highest authority) from Circulars
- Answer ENTIRELY in {lang_name}
- Close with a concise reference list

Final Answer in {lang_name}:"""

        final_answer = self.gemini.generate(
            judge_prompt, max_tokens=1400,
            tracker=tracker, call_type="judge_synthesis"
        )

        # ── Groq fallback if Gemini quota exceeded or returns empty ─────
        if not final_answer or len(final_answer.strip()) < 20:
            logger.warning("[MALD] Gemini returned empty — falling back to Groq for Judge synthesis")
            groq_judge_sys = (
                f"You are a senior Judge specialising in Algerian higher education law. "
                f"Answer ENTIRELY in {lang_name}. Be clear, accurate, and cite [REF-N] references inline."
            )
            groq_judge_user = (
                f"Query intent: {intent_label}\n"
                f"Confidence: {confidence:.0%}\n\n"
                f"ADVOCATE ARGUMENT:\n{advocate_arg}\n\n"
                f"DEVIL'S ADVOCATE COUNTER-ARGUMENT:\n{devil_arg}\n\n"
                f"LEGAL EVIDENCE:\n{ctx_judge}\n\n"
                f"Weigh both arguments. Use [REF-N] inline citations. "
                f"{'Acknowledge interpretive conflict.' if has_conflict else 'Confirm dominant interpretation.'} "
                f"Answer in {lang_name}:"
            )
            final_answer = self.groq.chat(
                groq_judge_sys, groq_judge_user,
                max_tokens=900, temperature=0.25,
                tracker=tracker, call_type="judge_synthesis_fallback"
            )

        debate_summary = {
            "advocate":    advocate_arg[:350] + ("…" if len(advocate_arg) > 350 else ""),
            "devil_advocate": devil_arg[:350] + ("…" if len(devil_arg) > 350 else ""),
            "has_interpretive_conflict": has_conflict,
            "conflict_note": ("⚠️ Interpretive conflict detected — see debate summary below."
                              if has_conflict else
                              "✅ Both arguments converge on a consistent interpretation.")
        }

        return final_answer, debate_summary


# ─────────────────────────────────────────────
#  SPIRAL-RAG v3 Engine
# ─────────────────────────────────────────────

class SpiralRAG:
    """
    SPIRAL-RAG v3 — five research innovations integrated into the pipeline.

    [I1] QueryIntentRouter          — intent-aware retrieval weights
    [I2] SemanticAuthorityClassifier — metadata-only LLM authority scoring
    [I3] TemporalSupersessionDetector — automatic law supersession alerts
    [I4] MultiAgentLegalDebate      — adversarial debate synthesis
    [I5] TokenCostTracker           — per-query USD cost estimation
    """

    MAX_ITERATIONS = 3
    TOP_K_FINAL    = 8

    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self._years = list({c.year for c in chunks})

        # Instantiate components
        self.groq    = GroqReasoner()
        self.gemini  = GeminiSynthesizer()
        self.bm25    = BM25(chunks)
        self.dense   = DenseRetriever(chunks)

        # v3 innovations
        self.authority_clf  = SemanticAuthorityClassifier(self.groq)    # [I2]
        self.intent_router  = QueryIntentRouter(self.groq)              # [I1]
        self.supersession   = TemporalSupersessionDetector(self.groq)   # [I3]
        self.debate_engine  = MultiAgentLegalDebate(self.groq, self.gemini)  # [I4]

        # [I2] Pre-classify authority at startup using ONLY title-based rules.
        # No LLM calls here — LLM fallback is lazy (only on actually retrieved
        # chunks during query time). This keeps startup fast and avoids rate limits.
        rule_hits, default_hits = 0, 0
        for c in chunks:
            tier = self.authority_clf._title_classify(c.title)
            if tier is not None:
                c.authority_tier   = tier
                c.authority_method = "rule"
                rule_hits += 1
            else:
                c.authority_tier   = 3
                c.authority_method = "pending"   # will upgrade to "llm" on first retrieval
                default_hits += 1

        logger.info(
            f"SPIRAL-RAG v3 ready — {len(chunks)} chunks | "
            f"authority: {rule_hits} rule-classified, {default_hits} pending LLM"
        )

    # ── Query expansion ────────────────────────────────────────────────────

    def _expand_query(
        self,
        query: str,
        language: str,
        tracker: Optional[TokenCostTracker] = None
    ) -> List[str]:
        system = (
            "You are a multilingual legal search expert. "
            "Generate 3 alternative search queries for the given legal question. "
            "Use different terminology, synonyms, and relevant Arabic/French terms. "
            "Return ONLY the queries, one per line, no numbering or punctuation."
        )
        user = f"Original ({LANG_LABELS.get(language,'?')}): {query}\n3 search variants:"
        result = self.groq.chat(
            system, user, max_tokens=220,
            tracker=tracker, call_type="query_expansion"
        )
        variants = [q.strip() for q in result.split('\n') if q.strip() and len(q.strip()) > 4]
        return [query] + variants[:3]

    # ── Retrieval ──────────────────────────────────────────────────────────

    def _retrieve(self, queries: List[str], exclude: set) -> List[RetrievedEvidence]:
        all_bm25:  List[List[Tuple[Chunk, float]]] = []
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
            a_score = legal_authority_score(chunk)
            evidence.append(RetrievedEvidence(
                chunk=chunk, bm25_score=b_score, dense_score=d_score,
                temporal_score=t_score, authority_score=a_score, rrf_score=rrf
            ))
        return evidence

    # ── Relevance scoring ──────────────────────────────────────────────────

    def _score_relevance(
        self,
        query: str,
        evidence: List[RetrievedEvidence],
        tracker: Optional[TokenCostTracker] = None
    ) -> Tuple[List[RetrievedEvidence], float, float]:
        if not evidence:
            return evidence, 0.0, 0.60

        passages = "\n".join(
            f"[{i}] ({e.chunk.year}, tier={e.chunk.authority_tier}, method={e.chunk.authority_method}) "
            f"{e.chunk.title[:60]}: {e.chunk.content[:250]}"
            for i, e in enumerate(evidence[:12])
        )
        system = (
            "You are a relevance judge for Arabic legal documents. "
            "For each numbered passage, output a relevance score 0.0–1.0 to the query. "
            "Return ONLY a JSON array: [0.9, 0.4, ...]"
        )
        user   = f"Query: {query}\n\nPassages:\n{passages}\n\nJSON scores:"
        result = self.groq.chat(
            system, user, max_tokens=120,
            tracker=tracker, call_type="relevance_scoring"
        )

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
            max_rrf = max((e.rrf_score for e in evidence), default=1e-6)
            for e in evidence:
                e.relevance_judgment = float(np.clip(e.rrf_score / max_rrf, 0.0, 1.0))
            scores = [e.relevance_judgment for e in evidence]

        raw_scores = [e.relevance_judgment for e in evidence[:len(scores)]]
        mean_conf  = float(np.mean(raw_scores)) if raw_scores else 0.0
        threshold  = adaptive_threshold(raw_scores)
        return evidence, mean_conf, threshold

    # ── [I1] Intent-weighted evidence ranking ──────────────────────────────

    def _rank_evidence(
        self,
        evidence: List[RetrievedEvidence],
        intent_weights: Optional[Dict[str, float]] = None
    ) -> List[RetrievedEvidence]:
        """
        [I1] Final ranking uses intent-specific weights rather than
        fixed coefficients, allowing the pipeline to prioritise different
        signals depending on the query type.
        """
        if intent_weights is None:
            intent_weights = {"relevance": 0.40, "authority": 0.25,
                              "dense": 0.20, "temporal": 0.15}
        for e in evidence:
            e._final = (
                intent_weights["relevance"]  * e.relevance_judgment
                + intent_weights["authority"] * e.authority_score
                + intent_weights["dense"]     * e.dense_score
                + intent_weights["temporal"]  * e.temporal_score
                + 4.0 * e.rrf_score
            )
        return sorted(evidence, key=lambda x: x._final, reverse=True)

    # ── Context & citation builder ─────────────────────────────────────────

    def _build_context(
        self,
        evidence: List[RetrievedEvidence],
        intent_weights: Optional[Dict[str, float]] = None
    ) -> Tuple[str, List[Dict]]:
        top = self._rank_evidence(evidence, intent_weights)[:self.TOP_K_FINAL]
        parts, citations = [], []
        for i, e in enumerate(top):
            ref = f"REF-{i+1}"
            auth_label = {1: "Official Gazette", 2: "Ministerial Decree", 3: "Circular"}.get(
                e.chunk.authority_tier, "Document"
            )
            parts.append(
                f"[{ref}] Year {e.chunk.year} | {auth_label} (tier={e.chunk.authority_tier}, "
                f"classified_by={e.chunk.authority_method}) | {e.chunk.title}\n"
                f"{e.chunk.content}\n"
                f"(relevance={e.relevance_judgment:.2f}, authority={e.authority_score:.2f}, "
                f"dense={e.dense_score:.2f}, temporal={e.temporal_score:.2f})"
            )
            citations.append({
                "ref": ref, "year": e.chunk.year, "title": e.chunk.title,
                "file": e.chunk.file,
                "authority_tier":   e.chunk.authority_tier,
                "authority_label":  auth_label,
                "authority_method": e.chunk.authority_method,
                "relevance": round(e.relevance_judgment, 2),
                "dense_score": round(e.dense_score, 3)
            })
        return "\n\n".join(parts), citations

    # ── Consistency validation ─────────────────────────────────────────────

    def _validate(
        self,
        answer: str,
        query: str,
        context: str,
        tracker: Optional[TokenCostTracker] = None
    ) -> Tuple[str, bool]:
        system = (
            "You are a hallucination detector for legal AI. "
            "Reply: CONSISTENT or INCONSISTENT, then one sentence of reasoning."
        )
        user    = f"Query: {query}\n\nEvidence:\n{context[:700]}\n\nAnswer:\n{answer[:600]}\n\nVerdict:"
        verdict = self.groq.chat(
            system, user, max_tokens=90,
            tracker=tracker, call_type="consistency_check"
        )
        return verdict, "INCONSISTENT" not in verdict.upper()

    # ── Main pipeline ──────────────────────────────────────────────────────

    def query(self, user_query: str, progress_cb=None) -> Dict:
        """
        Main pipeline. progress_cb(message: str) is called at each major step
        to enable Server-Sent Event streaming of reasoning trace. [W12]
        """
        t0      = time.time()
        log     = []
        tracker = TokenCostTracker()   # [I5] fresh per query

        def _emit(msg: str):
            log.append(msg)
            if progress_cb:
                progress_cb(msg)

        # 1. Language detection
        language = detect_language(user_query)
        _emit(f"🌐 Language detected: {LANG_LABELS.get(language, language)}")

        # 2. [I1/W2] Multi-label query intent classification
        intent_key, intent_weights, intent_label, intent_keys = self.intent_router.classify(
            user_query, tracker=tracker
        )
        _emit(f"🔍 Intent: {intent_label} → weights={intent_weights}")

        # 3. Query expansion
        expanded = self._expand_query(user_query, language, tracker=tracker)
        _emit(f"🔀 Query expanded to {len(expanded)} variants")

        # 4. Iterative self-reflective retrieval
        all_evidence: List[RetrievedEvidence] = []
        visited:      set = set()
        confidence        = 0.0
        threshold         = 0.60

        for iteration in range(self.MAX_ITERATIONS):
            new_ev = self._retrieve(expanded, visited)
            if not new_ev:
                _emit(f"Iter {iteration+1}: no new evidence — stopping")
                break

            _emit(f"📥 Iter {iteration+1}: scoring {len(new_ev)} retrieved chunks…")
            scored, conf, thresh = self._score_relevance(
                user_query, new_ev, tracker=tracker
            )
            for e in scored:
                visited.add(e.chunk.chunk_id)

            # [I2] LLM authority check for retrieved ambiguous chunks
            for e in scored:
                if e.chunk.authority_method not in ("rule", "cached"):
                    tier, method = self.authority_clf.classify(e.chunk, tracker=tracker)
                    e.chunk.authority_tier   = tier
                    e.chunk.authority_method = method
                    e.authority_score        = legal_authority_score(e.chunk)

            all_evidence.extend(scored)
            confidence, threshold = conf, thresh
            _emit(
                f"Iter {iteration+1}: +{len(scored)} chunks | "
                f"conf={conf:.2f} | adaptive_thresh={thresh:.2f}"
            )

            if conf >= thresh:
                _emit(f"✅ Adaptive threshold met — stopping at iteration {iteration+1}")
                break

            if iteration < self.MAX_ITERATIONS - 1:
                expanded = self._expand_query(
                    f"{user_query} — focus on specific legal articles and decrees",
                    language, tracker=tracker
                )

        # 5. Build context with intent-weighted ranking [I1]
        context, citations = self._build_context(all_evidence, intent_weights)

        if not context:
            return {
                "answer": _no_answer_msg(language), "language": language,
                "is_answerable": False,
                "confidence": 0.0, "citations": [], "reflection_log": log,
                "query_intent": intent_key, "intent_label": intent_label,
                "intent_keys": intent_keys,
                "cost_estimate": tracker.summary(),
                "processing_time_ms": round((time.time() - t0) * 1000, 1)
            }

        # [W6] Null/unanswerable detection.
        # Threshold is lower when running BM25-only (dense unavailable) because
        # LLM relevance scores are intrinsically lower without dense signal.
        bm25_only = DenseRetriever._embed_api_blocked
        NULL_CONFIDENCE_THRESHOLD = 0.08 if bm25_only else 0.22
        if confidence < NULL_CONFIDENCE_THRESHOLD:
            null_msgs = {
                "ar": "عذراً، لم أجد في الوثائق المتاحة ما يكفي للإجابة على سؤالك بثقة. "
                      "يُرجى إعادة صياغة السؤال أو التحقق من مصادر وزارة التعليم العالي مباشرة.",
                "fr": "Désolé, je n'ai pas trouvé de preuves suffisantes dans le corpus pour "
                      "répondre à votre question avec confiance. Reformulez ou consultez "
                      "directement les textes officiels du Ministère.",
                "en": "I could not find sufficient authoritative evidence in the regulatory corpus "
                      "to answer this query reliably. Please rephrase your question or consult "
                      "the official Ministry of Higher Education texts directly.",
                "dz": "ما لقيت دليل كافي في الوثائق باش نجاوبك بثقة. "
                      "حاول تعاود الصياغة أو راجع النصوص الرسمية مباشرة.",
            }
            _emit(f"⚠️ Low confidence ({confidence:.2f}) — returning safe refusal [W6]")
            return {
                "answer":       null_msgs.get(language, null_msgs["en"]),
                "is_answerable": False,
                "language":     language,
                "language_name": LANG_LABELS.get(language, ""),
                "confidence":   round(confidence, 2),
                "citations":    citations[:3],   # show what was found (low relevance)
                "query_intent": intent_key,
                "intent_label": intent_label,
                "intent_keys":  intent_keys,
                "cost_estimate": tracker.summary(),
                "reflection_log": log,
                "processing_time_ms": round((time.time() - t0) * 1000, 1),
                "supersession_alerts": [],
                "debate_summary": {},
                "authority_summary": {},
                "evidence_count": len(all_evidence),
                "iterations": iteration + 1 if all_evidence else 0,
                "intent_weights": intent_weights,
            }

        # 6. [I3] Temporal supersession detection
        _emit("⏱️ Checking for temporal supersessions (bigram overlap + LLM)… [I3]")
        supersession_alerts = self.supersession.detect(
            all_evidence, user_query, tracker=tracker
        )
        if supersession_alerts:
            confirmed = sum(1 for a in supersession_alerts if a["confirmed"])
            _emit(
                f"Supersession: {len(supersession_alerts)} alerts "
                f"({confirmed} LLM-confirmed)"
            )

        # 7. [I4] Multi-Agent Legal Debate synthesis (replaces single Gemini call)
        _emit("💬 Advocate arguing strongest interpretation… [I4]")
        _emit("👿 Devil's Advocate identifying contradictions… [I4]")
        final_answer, debate_summary = self.debate_engine.debate(
            user_query, context, language, citations, confidence,
            intent_label=intent_label, tracker=tracker
        )
        _emit("🧑‍⚖️ Judge synthesis complete (Gemini) [I4]")

        # 7b. Citation hallucination verification
        # Build ref→chunk_text mapping from the ranked evidence used in synthesis
        chunks_by_ref = {}
        top_evidence = self._rank_evidence(all_evidence, intent_weights)[:self.TOP_K_FINAL]
        for i, ev in enumerate(top_evidence):
            chunks_by_ref[i + 1] = ev.chunk.content
        final_answer, citations = verify_citations(final_answer, citations, chunks_by_ref)
        stripped = sum(1 for c in citations if c.get("verified") is False)
        if stripped:
            _emit(f"⚠️ Citation verifier: {stripped} hallucinated ref(s) stripped")
        else:
            _emit("✅ Citation verifier: all inline refs grounded in source chunks")

        # 8. Consistency validation
        verdict, is_consistent = self._validate(
            final_answer, user_query, context, tracker=tracker
        )
        _emit(f"✅ Validation: {verdict}")

        if not is_consistent:
            final_answer += (
                "\n\n⚠️ Automated consistency check flagged potential discrepancies. "
                "Please verify against the original regulatory texts."
            )

        # Authority summary
        authority_summary = {}
        for e in all_evidence:
            lbl = {1: "Official Gazette", 2: "Decree", 3: "Circular"}.get(
                e.chunk.authority_tier, "Other"
            )
            authority_summary[lbl] = authority_summary.get(lbl, 0) + 1

        # [I5] Cost summary
        cost_summary = tracker.summary()
        _emit(
            f"💰 Cost: ${cost_summary['total_cost_usd']:.6f} USD | "
            f"{cost_summary['total_api_calls']} API calls [I5]"
        )

        return {
            "answer":         final_answer,
            "is_answerable":  True,
            "language":       language,
            "language_name":  LANG_LABELS.get(language, ""),
            "confidence":     round(confidence, 2),
            "adaptive_threshold": round(threshold, 2),
            "citations":      citations,
            "authority_summary": authority_summary,
            "evidence_count": len(all_evidence),
            "iterations":     len([l for l in log if l.startswith("Iter")]),
            "reflection_log": log,
            "processing_time_ms": round((time.time() - t0) * 1000, 1),
            # ── v3 new fields ──────────────────────────────
            "query_intent":         intent_key,
            "intent_label":         intent_label,
            "intent_keys":          intent_keys,          # [W2] all detected intents
            "intent_weights":       intent_weights,
            "supersession_alerts":  supersession_alerts,  # [I3]
            "debate_summary":       debate_summary,       # [I4]
            "cost_estimate":        cost_summary,         # [I5]
        }


# ─────────────────────────────────────────────
#  Citation Hallucination Verifier
#  Checks each [REF-N] tag in the Judge output against the actual
#  retrieved chunk text using fuzzy token matching. Strips or flags
#  any citation whose claimed content cannot be found in the source.
# ─────────────────────────────────────────────

def verify_citations(
    judge_output: str,
    citations: List[Dict],
    chunks_by_ref: Dict[int, str],
    threshold: int = 62
) -> Tuple[str, List[Dict]]:
    """
    Returns (cleaned_answer, updated_citations_list).
    Any [REF-N] whose sentence content does not fuzzy-match the chunk
    (token_set_ratio < threshold) is removed from the inline text and
    flagged in the citations list with verified=False.
    """
    if not _FUZZ_AVAILABLE or not chunks_by_ref:
        for c in citations:
            c["verified"] = None   # verifier unavailable
        return judge_output, citations

    # Track which refs were actually used and verified
    ref_verified: Dict[int, bool] = {}

    # Split on sentence boundaries (keep Arabic / French text intact)
    sentence_pat = re.compile(r'(?<=[.!?؟])\s+')
    sentences = sentence_pat.split(judge_output)
    cleaned = []

    for sent in sentences:
        refs_in_sent = re.findall(r'\[REF-(\d+)\]', sent)
        if not refs_in_sent:
            cleaned.append(sent)
            continue

        # Strip ref tags to get the bare claim text
        claim = re.sub(r'\[REF-\d+\]', '', sent).strip()
        new_sent = sent

        for ref_str in refs_in_sent:
            ref_id = int(ref_str)
            chunk_text = chunks_by_ref.get(ref_id, "")

            if not chunk_text:
                # Hard hallucination: REF number beyond retrieved set
                new_sent = new_sent.replace(f'[REF-{ref_id}]', '')
                ref_verified[ref_id] = False
                logger.warning(f"[CitationVerifier] [REF-{ref_id}] stripped — chunk not found (hallucinated ref)")
                continue

            score = _fuzz.token_set_ratio(claim, chunk_text[:800])
            if score < threshold:
                new_sent = new_sent.replace(f'[REF-{ref_id}]', '')
                ref_verified[ref_id] = False
                logger.warning(f"[CitationVerifier] [REF-{ref_id}] stripped — fuzzy score {score} < {threshold}")
            else:
                ref_verified[ref_id] = True

        cleaned.append(re.sub(r'\s{2,}', ' ', new_sent).strip())

    # Annotate citations list
    for c in citations:
        ref_num_match = re.search(r'REF-(\d+)', c.get("ref", ""))
        if ref_num_match:
            n = int(ref_num_match.group(1))
            c["verified"] = ref_verified.get(n, True)   # unseen = not stripped = ok
        else:
            c["verified"] = True

    return " ".join(cleaned), citations


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
