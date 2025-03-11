# Ministry Regulation Q&A System (Arabic Language)

## 📌 Project Overview
The **Ministry Regulation Q&A System** is an intelligent chatbot designed to provide accurate and accessible information about Ministry regulations in Arabic. This system utilizes **Retrieval-Augmented Generation (RAG)** techniques to extract relevant information from official regulatory documents and deliver fact-based responses to user queries.

## 🎯 Objectives
- Develop a functional **prototype** by **April 16, 2024**.
- Build a **backend** that processes and indexes Arabic ministry regulation documents.
- Implement an **RAG-based retrieval system** to generate accurate answers.
- Create a **user-friendly Arabic chatbot interface**.
- Ensure system responses are **grounded in official ministry regulations**.
- Lay the foundation for a **scalable and maintainable** solution.

## 🏗️ Project Structure
```
Ministry-Regulation-QA/
│── backend/   # Code for the RAG system
│── frontend/  # Chatbot interface
│── docs/      # Project documentation
│── datasets/  # Arabic regulation documents
│── README.md  # Project overview
│── LICENSE    # License file
│── .gitignore # Ignore unnecessary files
```

## 🚀 Technologies Used
- **Python** (for backend processing and RAG system)
- **FastAPI** (for building the API)
- **LangChain** (for Retrieval-Augmented Generation)
- **OpenAI API / LLMs** (for generating responses)
- **MongoDB / PostgreSQL** (for storing indexed documents)
- **React.js / Next.js** (for frontend chatbot interface)
- **Docker** (for containerization and deployment)

## 📖 How to Set Up Locally
### 1️⃣ Clone the Repository
```bash
git clone https://github.com/YOUR-USERNAME/Ministry-Regulation-QA.git
cd Ministry-Regulation-QA
```

### 2️⃣ Install Dependencies
Backend:
```bash
cd backend
pip install -r requirements.txt
```
Frontend:
```bash
cd frontend
npm install
```

### 3️⃣ Run the Project
Backend:
```bash
uvicorn main:app --reload
```
Frontend:
```bash
npm run dev
```

## 👥 Team Members
- **Guenchi Samir** (Team Leader)
- **Youness Bensghir**
- **Salah Saadaoui**
- **Hocine Temrabet**

## 📌 Future Enhancements
- Expand coverage to **previous years' regulations**.
- Improve **accuracy and contextual understanding** of responses.
- Integrate with **external platforms** for wider accessibility.

---
✅ **License:** This project is licensed under the **MIT License**.
