from typing import TypedDict, Annotated, Sequence
from langgraph.graph import Graph, StateGraph, END
from groq import Groq
from graphrag.config import settings
from graphrag.models import QueryRequest, QueryResponse, Language, Citation
from graphrag.language_detector import LanguageDetector
from graphrag.guardrails import Guardrails
from graphrag.cache_manager import SemanticCacheManager
from graphrag.retriever import HybridRetriever
import time
import json
import logging

logger = logging.getLogger(__name__)


class GraphRAGState(TypedDict):
    """State for GraphRAG workflow"""
    query: str
    detected_language: Language
    response_language: Language
    is_safe: bool
    rejection_reason: str
    query_embedding: list
    cached_response: dict
    retrieved_docs: list
    retrieval_method: str
    citations: list
    graph_entities: list
    graph_relationships: list
    answer: str
    processing_time_ms: float
    cached: bool
    # Enhanced fields
    temporal_context: dict
    contradictions: list
    temporal_explanation: str
    contradiction_warning: str


class GraphRAGWorkflow:
    """LangGraph workflow for GraphRAG system with Groq API"""
    
    def __init__(self):
        self.lang_detector = LanguageDetector()
        self.guardrails = Guardrails()
        self.cache = SemanticCacheManager()
        self.retriever = HybridRetriever()
        
        # Initialize Groq client
        self.groq_client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        
        # Build workflow graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> Graph:
        """Build LangGraph workflow"""
        workflow = StateGraph(GraphRAGState)
        
        # Add nodes
        workflow.add_node("detect_language", self.detect_language)
        workflow.add_node("check_safety", self.check_safety)
        workflow.add_node("check_cache", self.check_cache)
        workflow.add_node("retrieve_documents", self.retrieve_documents)
        workflow.add_node("generate_answer", self.generate_answer)
        workflow.add_node("validate_citations", self.validate_citations)
        workflow.add_node("cache_response", self.cache_response)
        
        # Define edges
        workflow.set_entry_point("detect_language")
        workflow.add_edge("detect_language", "check_safety")
        
        # Conditional edge after safety check
        workflow.add_conditional_edges(
            "check_safety",
            lambda state: "safe" if state["is_safe"] else "unsafe",
            {
                "safe": "check_cache",
                "unsafe": END
            }
        )
        
        # Conditional edge after cache check
        workflow.add_conditional_edges(
            "check_cache",
            lambda state: "cached" if state.get("cached_response") else "retrieve",
            {
                "cached": END,
                "retrieve": "retrieve_documents"
            }
        )
        
        workflow.add_edge("retrieve_documents", "generate_answer")
        workflow.add_edge("generate_answer", "validate_citations")
        workflow.add_edge("validate_citations", "cache_response")
        workflow.add_edge("cache_response", END)
        
        return workflow.compile()
    
    def detect_language(self, state: GraphRAGState) -> GraphRAGState:
        """Detect input language and determine response language"""
        query = state["query"]
        
        detected_lang = self.lang_detector.detect_language(query)
        response_lang = self.lang_detector.get_response_language(detected_lang)
        
        logger.info(f"Detected: {detected_lang}, Response: {response_lang}")
        
        state["detected_language"] = detected_lang
        state["response_language"] = response_lang
        
        return state
    
    def check_safety(self, state: GraphRAGState) -> GraphRAGState:
        """Check query safety and domain constraints"""
        query = state["query"]
        detected_lang = state["detected_language"]
        
        is_safe, reason = self.guardrails.check_query_safety(query, detected_lang)
        
        state["is_safe"] = is_safe
        
        if not is_safe:
            state["rejection_reason"] = reason
            
            # Return JSON error for out-of-scope queries
            if settings.block_out_of_scope:
                error_response = {
                    "error": "Out of scope",
                    "reason": reason,
                    "message": self.guardrails.get_rejection_message(reason, detected_lang)
                }
                state["answer"] = json.dumps(error_response, ensure_ascii=False)
            else:
                state["answer"] = self.guardrails.get_rejection_message(reason, detected_lang)
            
            logger.warning(f"Query rejected: {reason}")
        
        return state
    
    def check_cache(self, state: GraphRAGState) -> GraphRAGState:
        """Check semantic cache for similar queries"""
        query = state["query"]
        
        # Generate query embedding
        query_embedding = self.retriever.embeddings.embed_query(query)
        state["query_embedding"] = query_embedding
        
        # Check cache
        cached = self.cache.get(query, query_embedding)
        
        if cached:
            state["cached_response"] = cached
            state["cached"] = True
            state["answer"] = cached.get("response", {}).get("answer", "")
            state["citations"] = cached.get("response", {}).get("citations", [])
            logger.info("Cache hit - returning cached response")
        
        return state
    
    def retrieve_documents(self, state: GraphRAGState) -> GraphRAGState:
        """Retrieve relevant documents using advanced hybrid search with all Phase 3 features"""
        query = state["query"]
        
        # Perform advanced retrieval with:
        # - Query expansion (synonyms, related terms)
        # - Multi-hop reasoning (for complex questions)
        # - Cross-encoder re-ranking (better relevance)
        # - Temporal reasoning (time-aware)
        # - Contradiction detection (conflict resolution)
        docs, method, enhancements = self.retriever.enhanced_retrieve_v2(
            query,
            max_results=5,
            use_graph=True,
            use_multi_hop=True,
            use_query_expansion=True,
            use_reranking=True
        )
        
        state["retrieved_docs"] = docs
        state["retrieval_method"] = method
        
        # Store all enhancements
        state["temporal_context"] = enhancements.get("temporal_context")
        state["contradictions"] = enhancements.get("contradictions", [])
        state["temporal_explanation"] = enhancements.get("temporal_explanation", "")
        state["contradiction_warning"] = enhancements.get("contradiction_warning", "")
        
        # Extract citations
        citations = self.retriever.extract_citations(docs)
        state["citations"] = [c.dict() for c in citations]
        
        # Log comprehensive retrieval info
        logger.info(
            f"Advanced retrieval complete: {len(docs)} documents using {method}. "
            f"Complex question: {enhancements.get('is_complex_question', False)}, "
            f"Query expanded: {enhancements.get('query_expansion') is not None}, "
            f"Re-ranked: {enhancements.get('reranking_summary') is not None}, "
            f"Temporal: {enhancements.get('temporal_context', {}).get('temporal_type', 'none')}, "
            f"Contradictions: {len(enhancements.get('contradictions', []))}"
        )
        
        return state
    
    def generate_answer(self, state: GraphRAGState) -> GraphRAGState:
        """Generate answer using Groq LLM with JSON output enforcement"""
        query = state["query"]
        docs = state["retrieved_docs"]
        response_lang = state["response_language"]
        detected_lang = state["detected_language"]
        
        # Get enhancements
        temporal_explanation = state.get("temporal_explanation", "")
        contradiction_warning = state.get("contradiction_warning", "")
        
        # Build context from retrieved documents
        context = "\n\n".join([
            f"[{i+1}] {doc.get('title', '')}\n{doc.get('content', '')}"
            for i, doc in enumerate(docs)
        ])
        
        # Add temporal context if available
        if temporal_explanation:
            context = f"{temporal_explanation}\n\n{context}"
        
        # System prompt with guardrails and JSON enforcement
        system_prompts = {
            Language.ARABIC: """أنت خبير قانوني متخصص في اللوائح والقوانين الوزارية الجزائرية، تتحدث بأسلوب ودود ومهني.

🎯 دورك:
- اشرح القوانين بطريقة واضحة وسهلة الفهم
- استخدم أمثلة عملية عندما يكون ذلك مناسباً
- اجعل إجابتك شاملة ومفيدة للمستخدم
- تحدث كخبير يساعد صديقاً، وليس كروبوت يسرد القوانين
- انتبه للسياق الزمني والتعارضات في المصادر

📋 قواعد مهمة:
1. ابدأ بشرح مبسط للموضوع قبل ذكر التفاصيل القانونية
2. اذكر أرقام القوانين والمواد بشكل طبيعي ضمن الشرح
3. اشرح الإجراءات خطوة بخطوة إذا كان السؤال يتعلق بإجراءات
4. أضف نصائح عملية عندما يكون ذلك مناسباً
5. إذا وجدت تعارض في المصادر، وضّح ذلك واشرح أي قانون يسود
6. إذا كان السؤال يتعلق بتاريخ معين، تأكد من استخدام القوانين السارية في ذلك الوقت
7. لا تقدم آراء سياسية أو شخصية
8. يجب أن تكون الإجابة بصيغة JSON

💡 أسلوب الإجابة:
- استخدم عبارات مثل: "دعني أشرح لك..."، "ببساطة..."، "المهم أن تعرف..."
- قسّم الإجابة إلى نقاط واضحة
- استخدم الرموز التعبيرية بشكل معتدل (✅ ❌ 📋 💡 ⚠️)
- اختم بنصيحة عملية أو خطوة تالية

صيغة JSON المطلوبة:
{
  "answer": "إجابة شاملة وودودة مع شرح مفصل",
  "citations": [
    {"law": "اسم القانون", "article": "رقم المادة", "excerpt": "مقتطف من النص"}
  ],
  "confidence": 0.95,
  "temporal_note": "ملاحظة زمنية إن وجدت",
  "warnings": ["تحذيرات أو تعارضات إن وجدت"]
}""",
            
            Language.ENGLISH: """You are a legal expert specializing in Algerian ministry regulations and laws. You speak in a friendly and professional manner.

🎯 Your Role:
- Explain laws in a clear and easy-to-understand way
- Use practical examples when appropriate
- Make your answer comprehensive and helpful to the user
- Talk like an expert helping a friend, not a robot listing laws

📋 Important Rules:
1. Start with a simplified explanation before mentioning legal details
2. Mention law and article numbers naturally within the explanation
3. Explain procedures step-by-step if the question is about procedures
4. Add practical advice when appropriate
5. If you don't find enough information, explain that clearly and suggest alternatives
6. Do not provide political or personal opinions
7. Response must be in JSON format

💡 Answer Style:
- Use phrases like: "Let me explain...", "Simply put...", "What's important to know..."
- Break down the answer into clear points
- Use emojis moderately (✅ ❌ 📋 💡)
- End with practical advice or next steps

Required JSON format:
{
  "answer": "Comprehensive and friendly answer with detailed explanation",
  "citations": [
    {"law": "Law name", "article": "Article number", "excerpt": "Text excerpt"}
  ],
  "confidence": 0.95
}""",
            
            Language.FRENCH: """Vous êtes un expert juridique spécialisé dans les règlements et lois ministériels algériens. Vous parlez de manière amicale et professionnelle.

🎯 Votre Rôle:
- Expliquez les lois de manière claire et facile à comprendre
- Utilisez des exemples pratiques lorsque c'est approprié
- Rendez votre réponse complète et utile pour l'utilisateur
- Parlez comme un expert aidant un ami, pas comme un robot listant des lois

📋 Règles Importantes:
1. Commencez par une explication simplifiée avant de mentionner les détails juridiques
2. Mentionnez les numéros de loi et d'article naturellement dans l'explication
3. Expliquez les procédures étape par étape si la question concerne des procédures
4. Ajoutez des conseils pratiques lorsque c'est approprié
5. Si vous ne trouvez pas suffisamment d'informations, expliquez-le clairement et suggérez des alternatives
6. Ne donnez pas d'opinions politiques ou personnelles
7. La réponse doit être au format JSON

💡 Style de Réponse:
- Utilisez des phrases comme: "Laissez-moi vous expliquer...", "En termes simples...", "Ce qui est important..."
- Divisez la réponse en points clairs
- Utilisez des emojis modérément (✅ ❌ 📋 💡)
- Terminez par un conseil pratique ou une prochaine étape

Format JSON requis:
{
  "answer": "Réponse complète et amicale avec explication détaillée",
  "citations": [
    {"law": "Nom de la loi", "article": "Numéro d'article", "excerpt": "Extrait du texte"}
  ],
  "confidence": 0.95
}"""
        }
        
        system_prompt = system_prompts.get(response_lang, system_prompts[Language.ARABIC])
        
        # Special handling for Darija: mention it in the prompt
        if detected_lang == Language.DARIJA:
            system_prompt += "\n\nملاحظة: السؤال مطروح بالدارجة المغربية، لكن يجب أن تكون الإجابة بالعربية الفصحى للدقة القانونية."
        
        # User prompt
        user_prompts = {
            Language.ARABIC: f"""المستخدم يسأل: {query}

السياق القانوني المتوفر:
{context}

{contradiction_warning if contradiction_warning else ""}

📝 المطلوب منك:
1. اشرح الموضوع بطريقة واضحة وودودة
2. ابدأ بمقدمة مبسطة عن الموضوع
3. اذكر القوانين والمواد ذات الصلة بشكل طبيعي ضمن الشرح
4. إذا كان السؤال عن إجراءات، اشرحها خطوة بخطوة
5. إذا وجدت تعارض في المصادر، وضّح أي قانون يسود ولماذا
6. إذا كان السؤال يتعلق بتاريخ معين، استخدم القوانين السارية في ذلك الوقت
7. اختم بنصيحة عملية أو معلومة مفيدة
8. استخدم أسلوب محادثة طبيعي وليس أسلوب رسمي جاف

قدم إجابة شاملة بصيغة JSON.""",
            
            Language.ENGLISH: f"""The user asks: {query}

Available legal context:
{context}

📝 What's required from you:
1. Explain the topic in a clear and friendly way
2. Start with a simplified introduction to the topic
3. Mention relevant laws and articles naturally within the explanation
4. If the question is about procedures, explain them step-by-step
5. End with practical advice or useful information
6. Use a natural conversational style, not a dry formal style

Provide a comprehensive answer in JSON format.""",
            
            Language.FRENCH: f"""L'utilisateur demande: {query}

Contexte juridique disponible:
{context}

📝 Ce qui est requis de vous:
1. Expliquez le sujet de manière claire et amicale
2. Commencez par une introduction simplifiée du sujet
3. Mentionnez les lois et articles pertinents naturellement dans l'explication
4. Si la question concerne des procédures, expliquez-les étape par étape
5. Terminez par un conseil pratique ou une information utile
6. Utilisez un style conversationnel naturel, pas un style formel sec

Fournissez une réponse complète au format JSON."""
        }
        
        user_prompt = user_prompts.get(response_lang, user_prompts[Language.ARABIC])
        
        # Generate answer using Groq with JSON enforcement
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Call Groq API with JSON mode
            completion = self.groq_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Slightly higher for more natural, conversational responses
                max_tokens=2000,
                response_format={"type": "json_object"} if settings.force_json_output else None
            )
            
            response_text = completion.choices[0].message.content
            
            # Parse JSON response
            try:
                response_json = json.loads(response_text)
                state["answer"] = response_json.get("answer", response_text)
                
                # Extract citations from JSON if available
                if "citations" in response_json:
                    json_citations = response_json["citations"]
                    for cit in json_citations:
                        if isinstance(cit, dict):
                            state["citations"].append({
                                "law_name": cit.get("law", "Unknown"),
                                "article_number": cit.get("article"),
                                "year": "Unknown",
                                "text_excerpt": cit.get("excerpt", ""),
                                "confidence": response_json.get("confidence", 0.8),
                                "source_file": None
                            })
            
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                state["answer"] = response_text
            
            logger.info(f"Generated answer using Groq ({self.model})")
        
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            error_msg = {
                Language.ARABIC: "عذراً، حدث خطأ في معالجة طلبك",
                Language.ENGLISH: "Sorry, an error occurred processing your request",
                Language.FRENCH: "Désolé, une erreur s'est produite lors du traitement de votre demande"
            }
            
            if settings.force_json_output:
                state["answer"] = json.dumps({
                    "error": "Processing error",
                    "message": error_msg.get(response_lang, error_msg[Language.ARABIC])
                }, ensure_ascii=False)
            else:
                state["answer"] = error_msg.get(response_lang, error_msg[Language.ARABIC])
        
        return state
    
    def validate_citations(self, state: GraphRAGState) -> GraphRAGState:
        """Validate that answer has proper citations"""
        answer = state["answer"]
        citations = state["citations"]
        
        if settings.require_citations:
            has_valid_citations = self.guardrails.validate_citation_requirement(answer, citations)
            
            if not has_valid_citations:
                logger.warning("Answer generated without proper citations")
                # Could add citation reminder to answer here
        
        return state
    
    def cache_response(self, state: GraphRAGState) -> GraphRAGState:
        """Cache the response for future similar queries"""
        query = state["query"]
        query_embedding = state["query_embedding"]
        
        response = {
            "answer": state["answer"],
            "citations": state["citations"],
            "retrieval_method": state["retrieval_method"]
        }
        
        self.cache.set(query, query_embedding, response)
        
        return state
    
    def process_query(self, request: QueryRequest) -> QueryResponse:
        """Process query through workflow"""
        start_time = time.time()
        
        # Initialize state
        initial_state = {
            "query": request.question,
            "detected_language": None,
            "response_language": None,
            "is_safe": True,
            "rejection_reason": None,
            "query_embedding": [],
            "cached_response": None,
            "retrieved_docs": [],
            "retrieval_method": "none",
            "citations": [],
            "graph_entities": [],
            "graph_relationships": [],
            "answer": "",
            "processing_time_ms": 0.0,
            "cached": False,
            # Enhanced fields
            "temporal_context": None,
            "contradictions": [],
            "temporal_explanation": "",
            "contradiction_warning": ""
        }
        
        # Run workflow
        final_state = self.workflow.invoke(initial_state)
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        # Build response
        response = QueryResponse(
            answer=final_state["answer"],
            detected_language=final_state["detected_language"],
            response_language=final_state["response_language"],
            citations=[Citation(**c) for c in final_state["citations"]],
            graph_entities=final_state.get("graph_entities"),
            graph_relationships=final_state.get("graph_relationships"),
            cached=final_state.get("cached", False),
            processing_time_ms=processing_time,
            retrieval_method=final_state["retrieval_method"]
        )
        
        return response
