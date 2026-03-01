# Pulse — Frontend

React + Vite + Tailwind CSS v4 glassmorphic medical AI dashboard.

## Quick Start

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

## Stack

- **React 18** (Vite 7)
- **Tailwind CSS v4** via `@tailwindcss/vite`
- **Lucide React** icons
- Glassmorphic dark UI with teal accents

## Pages

| Tab | Description |
|---|---|
| Dashboard | System health, patient stats, quick history lookup |
| Admin | Approve / reject pending doctors (admin-only) |
| Patients | Full CRUD, doctor linking, chronological history |
| Chat | Conversational symptom analysis with suggested prompts |
| Imaging | Upload medical images, view analysis, store results |

## Backend

The frontend expects the Pulse API at `http://127.0.0.1:8000/api/v1` (configurable on login).

