# Pulse AI Deployment Guide

This repository is set up for two separate deployments:

- Frontend: Vercel, using the static bundle in `frontend/dist`
- Backend: Hugging Face Spaces, using the root Docker deployment

Do not commit secrets. Keep all real values in deployment settings or local `.env` files only.

## 1) Prepare secrets locally

1. Copy `backend/.env.example` to `backend/.env` for local development only.
2. Fill in your real Supabase, Groq, and JWT values locally.
3. Keep `backend/.env` untracked. It is ignored by `.gitignore`.

## 2) Deploy the backend to Hugging Face Spaces

1. Create a new Hugging Face Space.
2. Choose the repository root as the Space source.
3. Set the Space SDK to `Docker`.
4. Keep `app_port` set to `7860`.
5. Use the root `Dockerfile` and root `main.py` already in this repo.
6. In Space settings, add these secrets:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `JWT_SECRET`
   - `GROQ_API_KEY` if you want Groq features enabled
7. In Space settings, add these variables:
   - `APP_NAME=Pulse API`
   - `APP_ENV=production`
   - `DEBUG=false`
   - `CORS_ORIGINS=*`
   - `SUPABASE_STORAGE_BUCKET=medical-records`
8. Wait for the build to finish.
9. Confirm the backend works at:
   - `/`
   - `/api/v1/health`

## 3) Point the frontend to the new backend

1. Open `frontend/dist/index.html`.
2. Replace `https://YOUR-BACKEND-SPACES-NAME.hf.space/api/v1` with your actual new Space URL.
3. Make sure the value ends with `/api/v1`.
4. Commit that change before deploying the frontend.

The frontend bundle reads `pulseApiBaseUrl` from browser storage and the bootstrap script writes the fallback value from `frontend/dist/index.html`.

## 4) Deploy the frontend to Vercel

1. Create a new Vercel project from the same GitHub repository.
2. Set the root directory to `frontend`.
3. Keep the existing `frontend/vercel.json` in place.
4. Deploy without adding server-side secrets.
5. Confirm the frontend loads and calls the backend Space URL you configured in `frontend/dist/index.html`.

## 5) Final validation

1. Open the Vercel URL in a private browser window.
2. Verify login, health, and any API-driven screens load without CORS errors.
3. Check the Space build logs if the backend returns 500s or 503s.
4. If the frontend still points at an old backend, clear browser storage for the site and reload.

## 6) Security rules

1. Never commit `backend/.env`.
2. Never paste real secrets into `frontend/dist/index.html` unless you intend them to be public.
3. Use Hugging Face Space secrets for backend credentials.
4. Use Vercel only for the static frontend bundle.