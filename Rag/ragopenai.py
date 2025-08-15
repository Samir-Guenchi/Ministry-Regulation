import json
import numpy as np
import google.generativeai as genai
import re
from typing import List, Tuple

genai.configure(api_key="AIzaSyDUhS7meZeHv7TfrxDbMXTbAv0pEN5KeKs")  

def normalize_arabic(text: str) -> str:
    text = re.sub(r'[ًٌٍَُِّْـ]', '', text) 
    text = re.sub(r'[إأآا]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'\s+', ' ', text)  
    return text.strip()
def load_chunks(json_path: str) -> List[dict]:
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        chunks = []
        for chunk in data:
            norm_title = normalize_arabic(chunk["title"])
            norm_content = normalize_arabic(chunk["content"])
            if len(norm_content) > 50:
                chunks.append({"title": norm_title, "content": norm_content})
        return chunks
    except FileNotFoundError:
        print(f"❌ File not found: {json_path}")
        return []
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in file: {json_path}")
        return []
def select_relevant_titles(chunks: List[dict], question: str) -> Tuple[List[int], str]:
    if not chunks:
        return [], ""
    titles_text = "\n".join([f"[{i}] {chunk['title']}" for i, chunk in enumerate(chunks)])
    prompt = f"""
اختر أرقام العناوين الأكثر صلة بالإجابة على السؤال التالي فقط:
السؤال: {question}

قائمة العناوين:
{titles_text}

أعطني قائمة الأرقام فقط، مفصولة بفواصل مثل: 2, 5, 7
"""
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    try:
        response = model.generate_content(prompt)
        if response and hasattr(response, 'text') and response.text:
            raw_answer = response.text.strip()
            selected_indices = re.findall(r'\d+', raw_answer)
            return list(map(int, selected_indices)), raw_answer
        else:
            print("❌ No valid response from Gemini API")
            return [], ""
    except Exception as e:
        print(f"❌ Gemini API Error: {str(e)}")
        return [], ""
def generate_final_answer(contents: List[str], question: str) -> str:
    print("\n📚 النصوص المسترجعة:\n")
    for i, content in enumerate(contents):
        print(f"[{i+1}] {content[:100]}...\n")

    context = "\n\n".join(contents)
    prompt = f"""
السؤال: {question}

باستخدام النصوص التالية، قدم إجابة دقيقة ومفصلة عن السؤال استنادا على القرارات و الملحق:

{context}
"""
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    try:
        response = model.generate_content(prompt)
        if response and hasattr(response, 'text') and response.text:
            return response.text.strip()
        else:
            return "⚠️ No valid response from Gemini API"
    except Exception as e:
        print(f"❌ Gemini API Error in generating answer: {str(e)}")
        return ""
def answer_implies_no_result(answer: str) -> bool:
    negative_phrases = [
        "لا يمكن", "لا يوجد", "لم أجد", "لا يتضمن", "لا يحتوي", "لا تتوفر", "لا تتطابق",
        "لا استطيع", "غير قادر", "لا توجد معلومات", "لا يُمكن", "لا يوفر ", "لا تحتوي", "وليس",
        "لا أستطيع", "لا يُقدم", "لا يوجد نص", "لا يقدم", "لا يذكر", "لا تتضمن", "لا توفر",
        "للأسف", "لا تقدم", "لا يمكنني", "لا توجد"
    ]
    return any(phrase in answer for phrase in negative_phrases)
if __name__ == '__main__':
    user_question = input("❓ اطرح سؤالك: ")
    normalized_question = normalize_arabic(user_question)
    json_files = [
        "./2022/2022_3.json",
        "./2022/2022_2.json",
        "./2022/2022_1.json",
        "./2022/2022_4.json",
    ]

    answer = ""
    for i, json_file in enumerate(json_files):
        print(f"\n📂 يتم التحقق من الملف {i+1}: {json_file}")
        chunks = load_chunks(json_file)
        if not chunks:
            continue
        selected_indices, _ = select_relevant_titles(chunks, normalized_question)
        selected_contents = [chunks[i]['content'] for i in selected_indices if i < len(chunks)]

        if selected_contents:
            answer = generate_final_answer(selected_contents, user_question)
            if not answer_implies_no_result(answer):
                break 

    if answer and not answer_implies_no_result(answer):
        print("\n📝 الإجابة:\n", answer)
    else:
        print("\n⚠️ لم يتم العثور على محتوى ذي صلة في أي من الملفات.")