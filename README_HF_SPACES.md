# Deploy Pulse Backend on Hugging Face Spaces (Docker)

This guide deploys the backend from this `backend/` folder to Hugging Face Spaces and connects your existing Vercel frontend.

## 1) Create the Space

1. Open Hugging Face and click **Create new Space**.
2. Select your account/org and set a Space name (example: `pulse-ai-backend`).
3. Set **SDK** to **Docker**.
4. Choose visibility (Public or Private).
5. Click **Create Space**.

## 2) Push backend folder contents to the Space repo root

Your Space repo root should contain files like:

- `main.py`
- `requirements.txt`
- `Dockerfile`
- `config/`, `routers/`, `services/`, `middleware/`, `models/`, `knowledge/`, `dependencies/`

Important:

- Do not push `.venv`, `.env`, or `__pycache__`.
- This backend already includes `Dockerfile` and `.dockerignore` for Space builds.

## 3) Add Space metadata in README.md

In the Space repo root, ensure `README.md` starts with:

```yaml
---
title: Pulse AI Backend
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---
```

After this YAML block, you can add any normal README content.

## 4) Configure Variables and Secrets in Space Settings

Open **Space -> Settings -> Variables and secrets** and add:

### Secrets

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `JWT_SECRET`
- `GROQ_API_KEY` (optional but recommended)

### Variables

- `APP_ENV=production`
- `DEBUG=false`
- `APP_NAME=Pulse API`
- `SUPABASE_STORAGE_BUCKET=medical-records`
- `CORS_ORIGINS=https://YOUR_VERCEL_DOMAIN`

If you use multiple origins, separate them with commas:

`CORS_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com`

## 5) Deploy

1. Push changes to your Space repository.
2. Open the **Build logs** tab and wait for success.
3. Test:
   - `https://<your-space>.hf.space/`
   - `https://<your-space>.hf.space/api/v1/health`

## 6) Connect your Vercel frontend

In Vercel project settings, add/update:

- `VITE_API_BASE_URL=https://<your-space>.hf.space`

Then redeploy frontend.

## 7) Validate full system

1. Open frontend in Vercel.
2. Login and call a protected endpoint.
3. Verify browser network requests go to `https://<your-space>.hf.space/api/v1/...`.
4. Confirm no CORS errors in browser console.

## Notes for free tier

- Free Space can sleep when idle (cold starts are expected).
- First request after sleep may take longer.
- Heavy ML requests may be slower on free CPU hardware.

If free-tier performance is not enough, keep this same Docker setup and move to paid hardware tier or another host without changing backend code.