# Model Files Directory

Place all `.pt` model files in this folder (`backend/models`).

Expected files:
- `fracture_model.pt`
- `tumor_model.pt`
- `kidney_stone_model.pt`
- `skin_model.pt` (EfficientNet-B0)

Notes:
- Grayscale images are routed to YOLO models.
- Color images are routed to `skin_model.pt`.
- If confidence is below `0.7`, Groq fallback is used.
