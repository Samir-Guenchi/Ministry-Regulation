from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from ragopenai import load_chunks, normalize_arabic, select_relevant_titles, generate_final_answer
import os

app = Flask(__name__)
CORS(app)

chunks = []

def load_data():
    global chunks
    chunks = load_chunks("newchunks.json")

load_data()

@app.route("/api/ask", methods=["POST"])
def ask():
    global chunks
    data = request.json
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400

    norm_question = normalize_arabic(question)
    selected_indices = select_relevant_titles(chunks, norm_question)
    selected_contents = [chunks[i]['content'] for i in selected_indices if i < len(chunks)]
    answer = generate_final_answer(selected_contents, question)
    return jsonify(
        {
            "answer": answer,
            "mimetype": "application/json; charset=utf-8"
        }
    )
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/chat')
def chat():
    return send_from_directory('.', 'chat.html')

if __name__ == "__main__":
    app.run(debug=True)