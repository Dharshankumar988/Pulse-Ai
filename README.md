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

This Space deploys the FastAPI backend from the `backend/` folder in this repository.

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
