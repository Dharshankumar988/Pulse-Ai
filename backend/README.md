# Pulse — Backend API

## Folder Structure

```
backend/
├── config/
│   ├── settings.py
│   └── supabase_client.py
├── middleware/
│   └── cors.py
├── models/
│   ├── auth_models.py
│   ├── medical_models.py
│   ├── ml_models.py
│   ├── multimodal_models.py
│   ├── patient_management_models.py
│   ├── postgres_schema.sql
│   └── supabase_models.py
├── dependencies/
│   └── auth.py
├── routers/
│   ├── api.py
│   ├── auth.py
│   ├── health.py
│   ├── medical.py
│   ├── ml.py
│   ├── multimodal.py
│   ├── patient_management.py
│   └── supabase.py
├── services/
│   ├── auth_service.py
│   ├── groq_service.py
│   ├── health_service.py
│   ├── knowledge_base_service.py
│   ├── ml_service.py
│   ├── multimodal_service.py
│   └── supabase_service.py
├── knowledge/
│   └── disease_knowledge_base.json
├── .env.example
├── .gitignore
├── main.py
├── README.md
└── requirements.txt
```

## 1) Create and Activate Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 2) Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3) Configure Environment Variables

Copy `.env.example` to `.env` and set values:

```env
APP_NAME=Pulse API
APP_ENV=production
DEBUG=false
CORS_ORIGINS=*
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-api-key
SUPABASE_STORAGE_BUCKET=medical-records
YOLO_FRACTURE_MODEL_PATH=./ml_models/yolov8_fracture.pt
YOLO_TUMOR_MODEL_PATH=./ml_models/yolov8_tumor.pt
YOLO_KIDNEY_STONE_MODEL_PATH=./ml_models/yolov8_kidney_stone.pt
EFFICIENTNET_MODEL_PATH=
MOBILENET_MODEL_PATH=
EFFICIENTNET_LABELS_PATH=
MOBILENET_LABELS_PATH=
ML_DEFAULT_CONFIDENCE=0.25
ML_DEFAULT_TOP_K=3
GROQ_API_KEY=
GROQ_MODEL=llama-3.1-8b-instant
GROQ_CACHE_TTL_SECONDS=600
```

## 4) Apply PostgreSQL Schema + Storage Bucket

Run [models/postgres_schema.sql](models/postgres_schema.sql) in Supabase SQL Editor.

It creates:
- `doctors`
- `patients`
- `records`
- public storage bucket `medical-records`

Schema highlights:
- `doctors.role`: `admin` or `doctor`
- `doctors.status`: `pending`, `approved`, `rejected`
- `records.status`: `pending`, `approved`, `rejected`

## 5) Run Locally

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 6) API Endpoints

- `GET /api/v1/health`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/validate`
- `POST /api/v1/doctors`
- `GET /api/v1/doctors`
- `GET /api/v1/doctors/{doctor_id}`
- `PUT /api/v1/doctors/{doctor_id}`
- `DELETE /api/v1/doctors/{doctor_id}`
- `POST /api/v1/patients`
- `GET /api/v1/patients`
- `GET /api/v1/patients/{patient_id}`
- `PUT /api/v1/patients/{patient_id}`
- `DELETE /api/v1/patients/{patient_id}`
- `POST /api/v1/records`
- `GET /api/v1/records`
- `GET /api/v1/records/{record_id}`
- `PUT /api/v1/records/{record_id}`
- `DELETE /api/v1/records/{record_id}`
- `POST /api/v1/records/{record_id}/image` (returns `public_url`)
- `GET /api/v1/ml/models/status`
- `POST /api/v1/ml/predict` (standardized inference output)
- `POST /api/v1/multimodal/analyze` (image and/or symptoms)
- `POST /api/v1/patient-management/patients`
- `GET /api/v1/patient-management/patients`
- `GET /api/v1/patient-management/patients/{patient_id}`
- `PUT /api/v1/patient-management/patients/{patient_id}`
- `DELETE /api/v1/patient-management/patients/{patient_id}`
- `POST /api/v1/patient-management/link` (link patient to doctor)
- `GET /api/v1/patient-management/patients/{patient_id}/doctors`
- `POST /api/v1/patient-management/analysis` (store analysis result)
- `GET /api/v1/patient-management/patients/{patient_id}/history?order=desc`
- `POST /api/v1/supabase/select`
- `POST /api/v1/supabase/insert`
- `POST /api/v1/supabase/update`
- `POST /api/v1/supabase/upload-image` (returns `public_url`)

## 8) ML Model Integration (Lazy Loading)

- Supported tasks:
	- `fracture` (YOLOv8)
	- `tumor` (YOLOv8)
	- `kidney_stone` (YOLOv8)
	- `skin_classification` (EfficientNet-B0 from `skin_model.pt`)
- Models are loaded only on first request for each task and then cached in memory.
- No eager loading at app startup, optimized for low-memory/free-tier cloud deployment.
- If a model path is missing or file is unavailable, API returns a clear service-unavailable error.
- All `.pt` files are loaded from `backend/models` (or `MODELS_DIRECTORY`).
- Routing uses OpenCV:
	- Grayscale image -> YOLO set (`fracture`, `tumor`, `kidney_stone`)
	- Color image -> EfficientNet-B0 skin model
- If confidence `< 0.7`, pipeline triggers Groq fallback for uncertainty-aware general analysis.

### Standardized Inference Output

Every `POST /api/v1/ml/predict` response follows:

```json
{
	"success": true,
	"task": "fracture",
	"model_name": "YOLOv8 Fracture",
	"model_type": "yolo",
	"predictions": [
		{
			"label": "fracture",
			"confidence": 0.94,
			"bbox": [120.0, 85.0, 260.0, 210.0]
		}
	],
	"metadata": {
		"num_detections": 1
	},
	"error": null
}
```

## 9) Multimodal Pipeline

- Endpoint: `POST /api/v1/multimodal/analyze`
- Accepts:
	- `file` (optional image)
	- `symptoms` (optional text)
- Behavior:
	- Detects grayscale vs color using OpenCV and routes accordingly.
	- If image routing is unknown or confidence is below `ML_LOW_CONFIDENCE_THRESHOLD`, sends a structured uncertainty prompt to Groq.
	- Uses Groq API for symptom analysis when `GROQ_API_KEY` is set.
	- If Groq is unavailable, uses rule-based symptom fallback.
	- Groq returns structured fields: `disease`, `probability`, `severity`, `risk`, `clinical_reasoning`, `follow_up_questions`, `missing_inputs`.
	- Repeated symptom text is cached in-memory (`GROQ_CACHE_TTL_SECONDS`) to minimize API usage and cost.
	- Fuses image + symptom signals with weighted logic (`image=0.6`, `symptoms=0.4`).
	- Returns response format:
		- `condition`
		- `confidence`
		- `risk_level`
		- `recommendation`
		- `notes`
	- Dynamically returns follow-up questions for missing/low-confidence input.
	- Drugs/procedures/tests are attached from JSON knowledge base mapping, not generated by LLM.

## 10) Knowledge Base Guardrail (No LLM Drug Generation)

- Disease-to-care mapping is stored in [knowledge/disease_knowledge_base.json](knowledge/disease_knowledge_base.json).
- Backend lookup in `knowledge_base_service.py` returns:
  - `drugs`
  - `procedures`
  - `tests`
- Groq prompts are restricted to diagnostic triage fields only and explicitly prohibit drugs/procedures/tests output.
- Final treatment-oriented suggestions in API responses come only from the JSON knowledge base.

## 11) Patient Management System

- CRUD operations are available for patients under `/api/v1/patient-management/patients`.
- Doctor-patient relationship is stored in `patient_doctors`.
- Analysis outputs are stored in `analysis_results` (disease, probability, severity, risk, uncertainty, recommendations, follow-up questions, sources).
- Chronological patient history endpoint merges `records` + `analysis_results` and sorts by timestamp.

## 7) Authentication and RBAC

- Login uses Supabase Auth email/password via `POST /api/v1/auth/login`.
- Access token validation uses `Authorization: Bearer <token>` on `GET /api/v1/auth/validate`.
- Doctor login is restricted if doctor status is not `approved`.
- Role checks:
	- `admin` + `approved` required for doctor management endpoints.
	- `doctor` or `admin` + `approved` required for patient/record endpoints.
	- Admin-only endpoints are available under `/api/v1/admin/*`.
	- Generic `/api/v1/supabase/*` endpoints are restricted to `admin` + `approved`.
- Approval is enforced from `doctors.status` (`pending`, `approved`, `rejected`).

### Admin Endpoints

- `GET /api/v1/admin/doctors/pending`
- `POST /api/v1/admin/doctors/{doctor_id}/approve`
- `POST /api/v1/admin/doctors/{doctor_id}/reject`

## Cloud Notes

- Keep secrets in environment variables only.
- Keep app stateless for free-tier/container deployments.
- Store images in Supabase Storage and persist only the returned URL.
