---
title: Pulse AI Backend
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Pulse AI Backend (Hugging Face Space)

Pulse AI is an advanced, AI-powered medical platform designed to assist in medical imaging analysis and patient management.

This Space automatically deploys the FastAPI backend container directly from the GitHub repository, running the models on Hugging Face infrastructure.

## Health endpoints

- `GET /`
- `GET /api/v1/health`

## Required Secrets

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `JWT_SECRET`
- `GROQ_API_KEY` (optional)

## Required Variables

- `APP_ENV=production`
- `DEBUG=false`
- `APP_NAME=Pulse API`
- `SUPABASE_STORAGE_BUCKET=medical-records`
- `CORS_ORIGINS=*`
