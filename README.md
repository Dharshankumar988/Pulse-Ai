---
title: Pulse AI Backend
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

<div align="center">
  <img src="https://raw.githubusercontent.com/Dharshankumar988/Pulse-AI/main/frontend/public/pulse-logo.svg" width="120" alt="Pulse AI Logo" onerror="this.src='https://upload.wikimedia.org/wikipedia/commons/4/42/Medical_icon.png'; this.width=100;"/>
  
  # 🩺 Pulse AI
  **Next-Generation Medical Diagnostics & Patient Management System**

  [![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
  [![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
  [![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org/)
  [![Ultralytics YOLO](https://img.shields.io/badge/YOLO-00FFFF?style=for-the-badge&logo=yolo&logoColor=black)](https://ultralytics.com/)
  [![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
</div>

<br />

## 📖 Overview

**Pulse AI** is an intelligent, end-to-end medical platform built for modern healthcare professionals. It bridges the gap between state-of-the-art **machine learning diagnostics** and robust **patient record management**. 

Whether it's detecting a microscopic bone fracture from an X-Ray, identifying brain tumors in MRI scans, or providing robust clinical reasoning via Groq's high-speed LLMs, Pulse AI acts as an invaluable, secure digital assistant for clinicians.

---

## ✨ Key Features

* 🧠 **AI-Powered Medical Imaging**: 
  * **Brain Tumors:** Highly accurate detection via YOLO models.
  * **Kidney Stones:** Automated localized identification.
  * **Bone Fractures:** Fast inference and bounding box generation.
  * **Skin Lesions:** Classification powered by PyTorch EfficientNet.
* ⚡ **Lazy-Loading ML Architecture**: Models are loaded into memory *only* when requested, ensuring minimal RAM overhead and rapid scaling.
* 💬 **Multimodal Clinical Reasoning**: Powered by **Groq AI**, the platform offers robust LLM-driven symptom analysis and treatment recommendations when standard imaging falls short.
* 🗄️ **Patient Management**: Securely store, retrieve, and update patient histories, prescriptions, and scans.
* 🔒 **Enterprise-Grade Security**: Fully protected by JWT authentication and Supabase Row Level Security (RLS).

---

## 🏗️ System Architecture

Pulse AI is structured as a decoupled monorepo:

* **Frontend:** A responsive, modern Single Page Application (SPA) built with React and Vite. Deployed automatically to **Vercel**.
* **Backend:** A high-performance Python/FastAPI server handling complex ML routing, model inference, and secure database interactions. Deployed as a Docker container to **Hugging Face Spaces**.
* **Database/Auth:** Hosted entirely on **Supabase** (PostgreSQL).

### 📁 Repository Structure

```text
Pulse-AI/
├── backend/               # FastAPI Server & ML logic
│   ├── models/            # .pt ML Model weights (Git LFS)
│   ├── routers/           # API Endpoint definitions
│   ├── services/          # Business logic (ML, Groq, Auth)
│   └── requirements.txt   # Python dependencies
├── frontend/              # React + Vite Application
│   ├── src/               # React components, pages, context
│   └── package.json       # Node dependencies
├── Dockerfile             # Production Docker configuration for Hugging Face
└── .github/workflows/     # CI/CD automated deployment scripts
```

---

## 🚀 Local Development Setup

To run Pulse AI locally, you will need to start both the backend and frontend servers.

### 1. Backend (FastAPI)

```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create a virtual environment and activate it
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure Environment Variables
cp .env.example .env
# Open .env and add your Supabase, JWT, and Groq credentials

# 5. Start the server
uvicorn main:app --reload --port 8000
```
*The backend API documentation will be available at `http://localhost:8000/docs`.*

### 2. Frontend (React)

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start the development server
npm run dev
```
*The web interface will be available at `http://localhost:5173`.*

---

## 🌍 Deployment

Pulse AI features a fully automated CI/CD pipeline.

### Continuous Integration
Any code pushed to the `main` branch automatically triggers deployment:
1. **Frontend:** Vercel detects the commit and builds the React application.
2. **Backend:** GitHub Actions (`sync-hf.yml`) pushes the repository and Git LFS models to Hugging Face Spaces.

### 🔐 Required Secrets (Production)
If deploying to a new environment, ensure these variables are securely set:
- `SUPABASE_URL` & `SUPABASE_KEY`
- `JWT_SECRET` *(Must be a highly secure, >32 byte string)*
- `GROQ_API_KEY`

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! 
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---
*Built with ❤️ for the future of healthcare technology.*
