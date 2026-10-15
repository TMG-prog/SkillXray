import os
import torch
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from transformers import AutoTokenizer, AutoModelForTokenClassification

app = FastAPI(title="SkillXray Extraction API")
security = HTTPBearer()

# Load directly from your Hugging Face Hub repository 
# (e.g., "tracy/jobbert_finetuned_knowledge" or your HF username)
MODEL_REPO = os.getenv("MODEL_REPO", "Tracymgprog/jobbert_finetuned_knowledge")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")

print(f"Downloading/loading model from Hugging Face: {MODEL_REPO}")
tokenizer = AutoTokenizer.from_pretrained('jjzha/jobbert_knowledge_extraction')
model = AutoModelForTokenClassification.from_pretrained(MODEL_REPO)
model.eval()

if torch.cuda.is_available():
    model = model.cuda()

@app.post("/api/v1/extract-skills")
async def extract_skills(payload: dict, credentials: HTTPAuthorizationCredentials = Security(security)):
    if MODEL_API_KEY and credentials.credentials != MODEL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid authorization token.")
    
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text field is required.")

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=160, return_offsets_mapping=True)
    offset_mapping = inputs.pop("offset_mapping")[0]
    
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        predictions = torch.argmax(outputs.logits, dim=-1)[0]

    extracted_skills = []
    current_span = []
    for idx, pred in enumerate(predictions.cpu().numpy()):
        if int(pred) in (1, 2):  # B-SKILL or I-SKILL
            start, end = int(offset_mapping[idx][0]), int(offset_mapping[idx][1])
            if start < end:
                current_span.append(text[start:end])
        elif current_span:
            skill_text = "".join(current_span).replace("##", "").strip()
            if len(skill_text) > 1:
                extracted_skills.append(skill_text)
            current_span = []

    unique_skills = list(dict.fromkeys(extracted_skills))
    gaps = [{"skill_name": skill, "gap_severity": 0.15} for skill in unique_skills]
    readiness_index = min(int((len(unique_skills) / 15) * 100), 100)

    return {
        "readiness_index": readiness_index,
        "gaps": gaps
    }