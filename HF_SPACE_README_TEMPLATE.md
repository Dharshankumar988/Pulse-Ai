---
title: Pulse AI Backend
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Pulse AI Backend

FastAPI backend for Pulse AI deployed on Hugging Face Spaces using Docker.

## Health Check

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
- `CORS_ORIGINS=https://YOUR_VERCEL_DOMAIN,https://YOUR_CUSTOM_DOMAIN`
