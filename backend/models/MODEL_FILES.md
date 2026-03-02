# Model Files Directory

Place all `.pt` model files in this folder (`backend/models`).

Expected files:
- `fracture_model.pt`
- `brain_model.pt` (used as tumor detector)
- `kidney_model.pt` (used as kidney-stone detector)
- `skin_model.pt` (EfficientNet-B0)

Notes:
- Grayscale images are routed only to radiology YOLO models (`fracture`, `tumor`, `kidney_stone`).
- Color images are routed to `skin_model.pt`.
- If confidence is below `0.7`, Groq fallback is used.
