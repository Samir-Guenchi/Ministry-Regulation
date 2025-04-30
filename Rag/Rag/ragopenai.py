import json
import numpy as np
import google.generativeai as genai
import re
from typing import List
import sys  #  Import the sys module

# === Set Gemini API key ===
genai.configure(api_key="AIzaSyDUhS7meZeHv7TfrxDbMXTbAv0pEN5KeKs")  # Replace with your actual Gemini API key

# === Arabic Normalization Function ===
def normalize_arabic(text: str) -> str:
    text = re.sub(r'[ًٌٍَُِّْـ]', '', text)  # Remove tashkeel
    text = re.sub(r'[إأآا]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'\s+', ' ', text)  # Normalize multiple spaces
    return text.strip()

# === Load JSON Data (title + content) ===
def load_chunks(json_path: str):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    chunks = []
    for chunk in data:
        norm_title = normalize_arabic(chunk["title"])
        norm_content = normalize_arabic(chunk["content"])
        if len(norm_content) > 50:
            chunks.append({"title": norm_title, "content": norm_content})
    return chunks

# === Step 1: Ask Gemini to pick relevant titles ===
def select_relevant_titles(chunks: List[dict], question: str) -> List[int]:
    titles = [chunk["title"] for chunk in chunks]
    model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")
    prompt = f"""
    باستخدام العناوين التالية فقط، حدد أكثر العناوين ملاءمة للإجابة على سؤال المستخدم. أجب بأرقام العناوين المفصولة بفواصل فقط.

    العناوين:
    {titles}

    سؤال المستخدم:
    {question}
    """
    response = model.generate_content(prompt)
    selected_indices = [int(i) - 1 for i in response.text.strip().split(",")]
    return list(map(int, selected_indices))

# === Step 2: Generate final answer based on selected contents ===
def generate_final_answer(contents: List[str], question: str) -> str:
    try:
        print("\n النصوص المسترجعة:\n".encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
    except UnicodeEncodeError:
        print("\n Retrieved Texts:\n")  #  Fallback to ASCII

    for i, content in enumerate(contents):
        try:
            print(f"[{i+1}] {content[:100]}...\n".encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        except UnicodeEncodeError:
            print(f"[{i+1}] ...\n")  #  Fallback

    context = "\n\n".join(contents)
    prompt = f"""
    السؤال: {question}

    باستخدام النصوص التالية، قدم إجابة دقيقة ومفصلة استنادا على القرارات و الملحق:
    {context}
    """
    model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip()

# === Main Execution ===
if __name__ == '__main__':
    json_file = "./newchunks.json"
    chunks = load_chunks(json_file)

    user_question = input("❓ اطرح سؤالك: ")
    normalized_question = normalize_arabic(user_question)

    selected_indices = select_relevant_titles(chunks, normalized_question)
    selected_contents = [chunks[i]['content'] for i in selected_indices if i < len(chunks)]
    final_answer = generate_final_answer(selected_contents, user_question)

    print("\n✅ الإجابة النهائية:\n", final_answer)