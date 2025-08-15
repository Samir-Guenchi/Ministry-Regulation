from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai
import os
import re
import json
import time
from langdetect import detect, DetectorFactory
import concurrent.futures
import logging
from google.api_core import exceptions
from typing import Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DetectorFactory.seed = 0

def normalize_text(text: str) -> str:
    text = re.sub(r'[ًٌٍَُِّْـ]', '', text) 
    text = re.sub(r'[إأآا]', 'ا', text)    
    text = re.sub(r'ى', 'ي', text)         
    text = re.sub(r'ة', 'ه', text)          
    text = re.sub(r'\s+', ' ', text)        
    return text.strip()

API_KEYS = {
    "2018": {"key": "AIzaSyD1rQKZaSdLZPJQlz3qNWDovG4CMpPaa6g", "last_used": 0, "delay": 2.0},
    "2019": {"key": "AIzaSyDm7jasqJYNH1HXJ5Wyc-DmTI0XD8dmqAY", "last_used": 0, "delay": 2.0},
    "2020": {"key": "AIzaSyBD8wquZaJramtLjthdFu7fgVwb0a9H06Q", "last_used": 0, "delay": 2.0},
    "2021": {"key": "AIzaSyD1gnAwJbgiYLmXx2EOUVXju8nN3fC5TAs", "last_used": 0, "delay": 2.0},
    "2022": {"key": "AIzaSyCUbAkT_ewPbKwuyTC5Xz1VpIhFtG2kif8", "last_used": 0, "delay": 2.0},
    "2023": {"key": "AIzaSyA-y_9Q8oCwmTJlhKbeSFXxICpNTgD-0NI", "last_used": 0, "delay": 2.0},
    "2024": {"key": "AIzaSyAtt4U3gS7g3dmbReVPF7nH5pGFD_Ww2JY", "last_used": 0, "delay": 2.0},
    "final": {"key": "AIzaSyAhy5zlNnPE9oxsxlDNalL5UDBljxiBxcI", "last_used": 0, "delay": 2.0}
}

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YEAR_TO_FILES = {
    "2018": [os.path.join(BASE_DIR, "2018", f"2018_{i}.json") for i in range(1, 5)],
    "2019": [os.path.join(BASE_DIR, "2019", f"2019_{i}.json") for i in [1, 3, 4]],
    "2020": [os.path.join(BASE_DIR, "2020", f"2020_{i}.json") for i in range(1, 5)],
    "2021": [os.path.join(BASE_DIR, "2021", f"2021_{i}.json") for i in range(1, 5)],
    "2022": [os.path.join(BASE_DIR, "2022", f"2022_{i}.json") for i in range(1, 5)],
    "2023": [os.path.join(BASE_DIR, "2023", f"2023_{i}.json") for i in range(1, 5)],
    "2024": [os.path.join(BASE_DIR, "2024", f"2024_{i}.json") for i in range(1, 4)],
}

def detect_language(text: str) -> str:
    try:
        lang = detect(text)
        return lang if lang in ['ar', 'en'] else 'en'
    except:
        return 'en'

def load_chunks(json_path: str) -> list:
    try:
        dir_path = os.path.dirname(json_path)
        os.makedirs(dir_path, exist_ok=True)

        if not os.path.exists(json_path):
            sample_data = [{
                "title": f"Sample Title for {os.path.basename(json_path)}",
                "content": f"This is sample content for {os.path.basename(json_path)}. It contains enough text to pass the length filter."
            }]
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(sample_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Created sample file: {json_path}")
            return sample_data
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        valid_chunks = []
        for chunk in data:
            try:
                if len(chunk.get("content", "")) > 50:
                    valid_chunks.append({
                        "title": normalize_text(chunk.get("title", "")),
                        "content": normalize_text(chunk.get("content", ""))
                    })
            except Exception as e:
                logger.warning(f"Invalid chunk in {json_path}: {e}")
                continue
                
        return valid_chunks
    except Exception as e:
        logger.error(f"Error loading {json_path}: {e}")
        return []
logger.info("Initializing data files...")
file_to_chunks = {}
for year, files in YEAR_TO_FILES.items():
    for file_path in files:
        file_to_chunks[file_path] = load_chunks(file_path)
logger.info("Data initialization complete.")

def process_single_year(year: str, question: str, max_retries=3) -> dict:
    """Process a single year and return results immediately without processing other years"""
    if year not in API_KEYS or year not in YEAR_TO_FILES:
        logger.warning(f"Invalid year or missing API key: {year}")
        return {"year": year, "results": [], "error": "Invalid year or missing API key"}
    
    results = []
    for attempt in range(max_retries):
        try:
            current_time = time.time()
            time_since_last_use = current_time - API_KEYS[year]["last_used"]
            if time_since_last_use < API_KEYS[year]["delay"]:
                time.sleep(API_KEYS[year]["delay"] - time_since_last_use)
            
            genai.configure(api_key=API_KEYS[year]["key"])
            API_KEYS[year]["last_used"] = time.time()
            
            year_has_data = any(
                file_to_chunks.get(file_path) and file_to_chunks[file_path]
                for file_path in YEAR_TO_FILES[year]
            )
            
            if not year_has_data:
                logger.info(f"No data available for year {year}")
                return {"year": year, "results": [], "error": "No data available"}
                
            model = genai.GenerativeModel(model_name="gemini-1.5-flash")
            
            for file_path in YEAR_TO_FILES[year]:
                chunks = file_to_chunks.get(file_path, [])
                if not chunks:
                    continue
                
                question_words = set(normalize_text(question).lower().split())
                relevant_indices = [
                    i for i, chunk in enumerate(chunks)
                    if (set(chunk['title'].lower().split()) & question_words or 
                        set(chunk['content'].lower().split()) & question_words)
                ]
                
                logger.info(f"Year {year}, file {file_path}: {len(relevant_indices)} relevant chunks found")
                
                if not relevant_indices:
                    continue
                
                if len(relevant_indices) > 10:
                    relevant_indices = relevant_indices[:10]
                lang = detect_language(question)
                if lang == 'ar':
                    prompt = f"""
                    اختر أرقام العناوين الأكثر صلة بالسؤال التالي فقط:
                    السؤال: {question}

                    قائمة العناوين:
                    {chr(10).join(f"[{j}] {chunks[i]['title']}" for j, i in enumerate(relevant_indices))}

                    أجب فقط بأرقام العناوين المختارة مفصولة بفواصل، مثال: 0, 2, 3
                    """
                else:
                    prompt = f"""
                    Select only the numbers of the titles most relevant to this question:
                    Question: {question}

                    Title list:
                    {chr(10).join(f"[{j}] {chunks[i]['title']}" for j, i in enumerate(relevant_indices))}

                    Respond only with the selected numbers separated by commas, e.g.: 0, 2, 3
                    """
                
                try:
                    response = model.generate_content(prompt)
                    if response and hasattr(response, 'text') and response.text:
                        selected_numbers = [int(num.strip()) for num in response.text.split(',') if num.strip().isdigit()]
                        selected_indices = [relevant_indices[num] for num in selected_numbers if num < len(relevant_indices)]
                        
                        if not selected_indices:
                            selected_indices = relevant_indices[:3]  
                            
                        results.extend({
                            "content": chunks[i]['content'],
                            "title": chunks[i]['title'],
                            "file": os.path.basename(file_path),
                            "year": year
                        } for i in selected_indices)
                except Exception as e:
                    logger.error(f"Error in selection for {file_path}: {e}")
                    results.extend({
                        "content": chunks[i]['content'],
                        "title": chunks[i]['title'],
                        "file": os.path.basename(file_path),
                        "year": year
                    } for i in relevant_indices[:3]) 
            
            return {"year": year, "results": results[:5]}  
            
        except exceptions.RetryError:
            if attempt == max_retries - 1:
                logger.error(f"Max retries reached for year {year}")
                return {"year": year, "results": [], "error": "Max retries reached"}
            time.sleep(2 ** attempt)  
        except Exception as e:
            logger.error(f"Error processing year {year}: {e}")
            return {"year": year, "results": [], "error": str(e)}
    
    return {"year": year, "results": [], "error": "Unknown error"}

def generate_final_answer(year_results: dict, question: str, lang: str) -> str:
    try:
        current_time = time.time()
        time_since_last_use = current_time - API_KEYS["final"]["last_used"]
        if time_since_last_use < API_KEYS["final"]["delay"]:
            time.sleep(API_KEYS["final"]["delay"] - time_since_last_use)

        genai.configure(api_key=API_KEYS["final"]["key"])
        API_KEYS["final"]["last_used"] = time.time()
        
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        
        context_parts = []
        for year_data in year_results.values():
            if year_data.get("results"):
                year = year_data["year"]
                contents = [r["content"] for r in year_data["results"]]
                context_parts.append(f"=== Results from {year} ===\n" + "\n".join(contents[:3])) 
        
        if not context_parts:
            prompt = f"""
            {'لا يوجد سياق متاح. قدم إجابة عامة باللغة العربية:' if lang == 'ar' else 'No context available. Provide a general answer in English:'}
            السؤال/Question: {question}
            """
        else:
            full_context = "\n\n".join(context_parts)
            prompt = f"""
            {'أجب باللغة العربية بناءً على السياق التالي:' if lang == 'ar' else 'Answer in English based on this context:'}
            السؤال/Question: {question}
            
            السياق/Context:
            {full_context}
            
            {'قدم إجابة واضحة ومنظمة مع ذكر المصادر إن أمكن.' if lang == 'ar' else 'Provide a clear, organized answer citing sources if possible.'}
            """
        
        response = model.generate_content(prompt)
        return response.text if response and hasattr(response, 'text') else (
            "⚠️ لا توجد إجابة متاحة" if lang == 'ar' else "⚠️ No answer available"
        )
    except Exception as e:
        logger.error(f"Error generating final answer: {e}")
        return "⚠️ حدث خطأ أثناء معالجة طلبك" if lang == 'ar' else "⚠️ Error processing your request"
SENSITIVE_TOPICS = {
    'ar': ["فلسطين", "إسرائيل", "الصراع العربي الإسرائيلي", "حزب الله", "حماس", "الجهاد الإسلامي"],
    'en': ["palestine", "israel", "gaza", "west bank", "hamas", "hezbollah", "middle east conflict"]
}

BANNED_PATTERNS = {
    'ar': ["قتل", "تفجير", "إرهاب", "عنف"],
    'en': ["kill", "bomb", "terror", "violence"]
}

def analyze_query_safety(question: str) -> Tuple[bool, str]:
    """
    Analyze if the query contains sensitive or banned content.
    Returns (is_safe, reason) where:
    - is_safe: True if question is safe to process
    - reason: Explanation if not safe
    """
    lang = detect_language(question)
    normalized_question = normalize_text(question).lower()
    for topic in SENSITIVE_TOPICS.get(lang, []):
        if normalize_text(topic).lower() in normalized_question:
            return (False, "political_topic")
    for pattern in BANNED_PATTERNS.get(lang, []):
        if normalize_text(pattern).lower() in normalized_question:
            return (False, "violent_content")
    return (True, "")


@app.route("/")
def index():
    return send_from_directory('.', 'index.html')

@app.route("/chat")
def chat():
    return send_from_directory('.', 'chat.html')

@app.route("/api/stats")
def get_stats():
    stats = {
        "years": {},
        "total_files": 0,
        "total_chunks": 0,
        "api_keys": list(API_KEYS.keys())
    }

    for year, files in YEAR_TO_FILES.items():
        year_chunks = sum(len(file_to_chunks.get(file_path, [])) for file_path in files)
        valid_files = sum(1 for file_path in files if file_path in file_to_chunks and file_to_chunks[file_path])
        
        stats["years"][year] = {
            "files": len(files),
            "valid_files": valid_files,
            "chunks": year_chunks
        }
        stats["total_files"] += valid_files
        stats["total_chunks"] += year_chunks
        
    return jsonify(stats)

# Modify your ask() endpoint to include the safety check
@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.json
    question = data.get("question", "").strip()
    preferred_lang = data.get("language", None)

    if not question or len(question) < 3:
        return jsonify({"error": "Question too short or empty"}), 400

    # Safety check - analyze the query before processing
    is_safe, reason = analyze_query_safety(question)
    if not is_safe:
        lang = preferred_lang if preferred_lang in ['ar', 'en'] else detect_language(question)
        if reason == "political_topic":
            msg = "نعتذر، لا يمكننا معالجة الأسئلة المتعلقة بالمواضيع السياسية الحساسة" if lang == 'ar' else "We apologize, we cannot process questions about sensitive political topics"
        else:
            msg = "نعتذر، لا يمكننا معالجة هذا النوع من الاستفسارات" if lang == 'ar' else "We apologize, we cannot process this type of inquiry"
        return jsonify({"error": msg}), 400

    lang = preferred_lang if preferred_lang in ['ar', 'en'] else detect_language(question)

    logger.info(f"Processing question: '{question}' in {lang}")

    # Rest of your existing ask() implementation...
    year_results = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_year = {
            executor.submit(process_single_year, year, question): year
            for year in YEAR_TO_FILES.keys()
        }
        
        for future in concurrent.futures.as_completed(future_to_year):
            year = future_to_year[future]
            try:
                result = future.result()
                year_results[year] = result
                logger.info(f"Year {year} returned {len(result.get('results', []))} results")
            except Exception as e:
                logger.error(f"Failed to process year {year}: {e}")
                year_results[year] = {"year": year, "results": [], "error": str(e)}

    final_answer = generate_final_answer(year_results, question, lang)

    return jsonify({
        "answer": final_answer,
        "language": lang,
        "year_results": year_results
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)