from fastapi import FastAPI, HTTPException
import uvicorn
import logging
from services.extractor import extract as run_extraction
from services.analyzer import analyze as run_analysis
from models.extract import ExtractionRequest
from models.analyze import AnalysisRequest, AnalysisResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Match Intel — AI Service")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "match-intel-ai"}

@app.post("/extract")
async def extract(request: ExtractionRequest):
    return await run_extraction(request)

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    return await run_analysis(request)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)