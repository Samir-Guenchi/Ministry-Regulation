"""
SPIRAL-RAG Flask Application — v3 (Research Edition)
Self-reflective Parallel Iterative Retrieval with Adaptive Language
"""

import os
import re
import json
import logging
import queue as q_module
import threading
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS

from rag_core import load_all_chunks, SpiralRAG, detect_language, LANG_LABELS

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ─── App Setup ───────────────────────────────
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

# ─── Load data & build RAG engine ────────────
logger.info("Loading document corpus...")
chunks = load_all_chunks(DATA_DIR)
engine = SpiralRAG(chunks)
logger.info(f"SPIRAL-RAG v3 ready. {len(chunks)} chunks indexed.")

# ─── Safety Guardrails ────────────────────────
SENSITIVE_TOPICS = [
    "palestine", "israel", "gaza", "hamas", "hezbollah",
    "فلسطين", "إسرائيل", "حماس", "حزب الله",
    "palestin", "israël", "terroris"
]

BANNED_PATTERNS = ["kill", "bomb", "terror", "violence", "قتل", "تفجير", "إرهاب"]


def is_safe_query(question: str) -> tuple:
    q_lower = question.lower()
    for topic in SENSITIVE_TOPICS:
        if topic in q_lower:
            return False, "political_topic"
    for pat in BANNED_PATTERNS:
        if pat in q_lower:
            return False, "violent_content"
    return True, ""


def safety_message(reason: str, lang: str) -> str:
    msgs = {
        "political_topic": {
            "ar": "نعتذر، لا يمكننا معالجة الأسئلة السياسية الحساسة.",
            "fr": "Désolé, nous ne pouvons pas traiter les questions politiques sensibles.",
            "en": "Sorry, we cannot process sensitive political topics.",
            "dz": "آسف، ما نقدرش نعالجو المواضيع السياسية الحساسة."
        },
        "violent_content": {
            "ar": "نعتذر، لا يمكننا معالجة هذا الاستفسار.",
            "fr": "Désolé, nous ne pouvons pas traiter cette demande.",
            "en": "Sorry, we cannot process this type of inquiry.",
            "dz": "آسف، ما نقدرش نعالجو هذا الطلب."
        }
    }
    return msgs.get(reason, msgs["violent_content"]).get(lang, msgs[reason]["en"])


# ─── Routes ──────────────────────────────────

@app.route("/")
def index():
    return send_from_directory('.', 'index.html')


@app.route("/chat")
def chat():
    return send_from_directory('.', 'chat.html')


def _format_result(result: dict, fallback_lang: str = "en") -> dict:
    """Shared formatter for both /api/ask and /api/stream responses."""
    lang = result.get("language", fallback_lang)
    return {
        # ── Core fields ───────────────────────────────────────────────
        "answer":               result["answer"],
        "is_answerable":        result.get("is_answerable", True),
        "language":             lang,
        "language_name":        LANG_LABELS.get(lang, ""),
        "confidence":           result.get("confidence", 0.0),
        "adaptive_threshold":   result.get("adaptive_threshold", 0.6),
        "citations":            result.get("citations", []),
        "authority_summary":    result.get("authority_summary", {}),
        "evidence_count":       result.get("evidence_count", 0),
        "iterations":           result.get("iterations", 1),
        "reflection_log":       result.get("reflection_log", []),
        "processing_time_ms":   result.get("processing_time_ms", 0),
        # ── v3 innovation fields ──────────────────────────────────────
        "query_intent":         result.get("query_intent", "definitional"),
        "intent_label":         result.get("intent_label", "📖 Definitional"),
        "intent_keys":          result.get("intent_keys", []),          # [W2]
        "intent_weights":       result.get("intent_weights", {}),
        "supersession_alerts":  result.get("supersession_alerts", []),  # [I3]
        "debate_summary":       result.get("debate_summary", {}),       # [I4]
        "cost_estimate":        result.get("cost_estimate", {}),        # [I5]
    }


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    question       = data.get("question", "").strip()
    preferred_lang = data.get("language", None)

    if not question or len(question) < 3:
        return jsonify({"error": "Question too short or empty"}), 400
    if len(question) > 600:
        return jsonify({"error": "Question too long (max 600 characters)"}), 400

    lang = preferred_lang if preferred_lang in ["ar", "en", "fr", "dz"] else detect_language(question)

    safe, reason = is_safe_query(question)
    if not safe:
        return jsonify({"error": safety_message(reason, lang)}), 400

    logger.info(f"Query [{lang}]: {question[:80]}…")

    try:
        result = engine.query(question)
        return jsonify(_format_result(result, lang))
    except Exception as e:
        logger.exception(f"Error processing query: {e}")
        return jsonify({"error": "An internal error occurred. Please try again."}), 500


@app.route("/api/stream", methods=["POST"])
def stream_ask():
    """
    [W12] SSE streaming endpoint. Sends real reasoning-trace events while
    the pipeline runs, then the final result — eliminating dead-silence wait.

    Client reads this with fetch() + ReadableStream (not EventSource, which
    only supports GET). Each event is a JSON line prefixed with 'data: '.
    """
    data = request.get_json(force=True)
    question       = data.get("question", "").strip()
    preferred_lang = data.get("language", None)
    lang = preferred_lang if preferred_lang in ["ar","en","fr","dz"] else detect_language(question)

    def _sse(obj: dict) -> str:
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

    def error_stream(msg: str):
        yield _sse({"type": "error", "message": msg})

    if not question or len(question) < 3:
        return Response(error_stream("Question too short or empty"),
                        mimetype="text/event-stream")
    if len(question) > 600:
        return Response(error_stream("Question too long (max 600 characters)"),
                        mimetype="text/event-stream")

    safe, reason = is_safe_query(question)
    if not safe:
        return Response(error_stream(safety_message(reason, lang)),
                        mimetype="text/event-stream")

    event_q: q_module.Queue = q_module.Queue()

    def run():
        try:
            def progress_cb(msg: str):
                event_q.put(("status", msg))
            result = engine.query(question, progress_cb=progress_cb)
            event_q.put(("done", result))
        except Exception as exc:
            logger.exception(f"Stream pipeline error: {exc}")
            event_q.put(("error", str(exc)))

    threading.Thread(target=run, daemon=True).start()

    @stream_with_context
    def generate():
        while True:
            try:
                etype, payload = event_q.get(timeout=90)
                if etype == "status":
                    yield _sse({"type": "status", "message": payload})
                elif etype == "done":
                    yield _sse({"type": "done", "result": _format_result(payload, lang)})
                    break
                else:
                    yield _sse({"type": "error", "message": str(payload)})
                    break
            except q_module.Empty:
                yield _sse({"type": "heartbeat"})   # keep connection alive

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control":    "no-cache",
        "X-Accel-Buffering": "no",
        "Connection":       "keep-alive",
    })


@app.route("/api/stats")
def stats():
    year_counts = {}
    for chunk in chunks:
        year_counts[chunk.year] = year_counts.get(chunk.year, 0) + 1

    # Authority method breakdown
    method_counts = {}
    for chunk in chunks:
        method_counts[chunk.authority_method] = method_counts.get(chunk.authority_method, 0) + 1

    return jsonify({
        "total_chunks":       len(chunks),
        "by_year":            year_counts,
        "architecture":       "SPIRAL-RAG v3",
        "version":            "v3",
        "llms": {
            "reasoning":       "Groq llama-3.3-70b-versatile",
            "synthesis":       "Google Gemini 2.0 Flash (Judge in MALD)",
            "embedding":       "Gemini Embedding-001 (dense, 768-dim)"
        },
        "languages_supported":  list(LANG_LABELS.values()),
        "max_iterations":       SpiralRAG.MAX_ITERATIONS,
        "confidence_threshold": "adaptive (IQR-based, per query)",
        "retrieval":            "BM25 + Gemini Dense Embeddings via RRF",
        "innovations_v3": {
            "I1_query_intent_routing":          True,
            "I2_semantic_authority_classifier": True,
            "I3_temporal_supersession":         True,
            "I4_multi_agent_legal_debate":      True,
            "I5_token_cost_tracker":            True,
        },
        "authority_method_breakdown": method_counts,
    })


@app.route("/api/health")
def health():
    groq_ok   = bool(os.environ.get("GROQ_API_KEY"))
    gemini_ok = bool(os.environ.get("GEMINI_API_KEY"))
    return jsonify({
        "status":           "healthy" if (groq_ok and gemini_ok) else "degraded",
        "groq_configured":  groq_ok,
        "gemini_configured": gemini_ok,
        "corpus_loaded":    len(chunks) > 0,
        "chunk_count":      len(chunks),
        "version":          "v3"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
