---
title: Pulse AI Backend
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# 🩺 Pulse AI

<div align="center">
  <h3>Next-Generation Medical Imaging & Patient Management Platform</h3>
</div>

<br />

Pulse AI is an advanced, AI-powered medical platform designed to seamlessly integrate diagnostic machine learning models with a modern patient management system. This repository contains the **FastAPI backend** and the ML inference pipeline.

This branch (`main`) is automatically deployed to [Hugging Face Spaces](https://huggingface.co/spaces) using a robust GitHub Actions CI/CD pipeline.

---

## ✨ Core Features

- **🧠 Multi-Model Medical Imaging Analysis:**
  - **Brain Tumors:** Highly accurate detection via YOLO models.
  - **Kidney Stones:** Automated localized identification.
  - **Bone Fractures:** Fast inference and bounding box generation.
  - **Skin Lesions:** Classification powered by EfficientNet.
- **⚡ Lazy-Loading ML Architecture:** Memory-efficient model loading ensures minimal overhead and rapid scaling.
- **💬 Groq AI Multimodal Integration:** Fallback symptom analysis and robust clinical reasoning powered by Groq's high-speed LLaMA models.
- **🔒 Secure Authentication:** JWT-based user and clinician authentication.
- **🗄️ Supabase Cloud Storage:** Real-time medical record synchronization and secure storage.

## 🛠️ Tech Stack

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11)
- **Machine Learning:** [Ultralytics YOLO](https://docs.ultralytics.com/), [PyTorch](https://pytorch.org/)
- **LLM Integration:** [Groq AI](https://groq.com/)
- **Database / Auth:** [Supabase](https://supabase.com/)
- **Deployment:** Docker, Hugging Face Spaces

---

## 🚀 API Endpoints

The backend exposes a full suite of RESTful API endpoints. Below are some of the key health and inference routes:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Root API status |
| `GET` | `/api/v1/health` | Detailed healthcheck of database and models |
| `POST` | `/api/v1/multimodal/analyze` | Submit images/symptoms for AI analysis |
| `GET` | `/api/v1/patient-management/patients` | Retrieve patient records (Requires Auth) |

*Full API documentation (Swagger UI) is available at `/docs` when the server is running.*

---

## ⚙️ Environment Configuration

To run this backend locally or deploy it, the following environment variables are required. For security, never commit `.env` files.

### Secrets (Must be kept secure)
- `SUPABASE_URL`: Your Supabase project URL.
- `SUPABASE_KEY`: Your Supabase Anon/Service Role Key.
- `JWT_SECRET`: Secure cryptographic key (must be > 32 bytes for HS256).
- `GROQ_API_KEY`: Required for multimodal LLM features.

### Application Variables
- `APP_ENV=production`
- `DEBUG=false`
- `APP_NAME=Pulse API`
- `SUPABASE_STORAGE_BUCKET=medical-records`
- `CORS_ORIGINS=*` *(Configure specifically for your Vercel frontend in production)*

---

## 🌍 Continuous Deployment

This repository features automated CI/CD. 
Any push to the `main` branch will trigger a GitHub Action (`sync-hf.yml`) that securely pushes the updated containerized environment and Git LFS objects to Hugging Face Spaces. 

* **Frontend:** Deploys automatically to Vercel.
* **Backend:** Deploys automatically to Hugging Face Spaces using the root `Dockerfile`.
