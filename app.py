from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os
import time
import uuid
import shutil
from pydub import AudioSegment
import threading

# Import custom modules
# Don't import process_pipeline directly to avoid module-level execution in pipeline.py
from utils.LLM import findsolution 
from utils.translate import chunk_text, translate_text
import requests
from sarvamai import SarvamAI
from sarvamai.play import save
import io
import dotenv

# Load environment variables
dotenv.load_dotenv()
SARVAM_AI_API = os.environ.get("SARVAM_AI_API")

# Create FastAPI app
app = FastAPI(title="Voice Processing API", 
              description="API for processing voice inputs, translating, and providing information about Bengali culture and heritage")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
os.makedirs("audio_chunks", exist_ok=True)
os.makedirs("responses", exist_ok=True)

# Track processing status
processing_status = {}

@app.get("/")
async def root():
    """Root endpoint to check if API is running"""
    return {"message": "Voice Processing API is running"}

@app.post("/process-audio/")
async def process_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Process uploaded audio file through the complete pipeline:
    1. Convert speech to text
    2. Generate response about Bengali culture using Gemini
    3. Translate to Bengali
    4. Convert Bengali text to speech
    """
    # Generate a unique ID for this request
    request_id = str(uuid.uuid4())
    
    # Create a temporary file to store the uploaded audio
    audio_path = f"audio_chunks/upload_{request_id}.wav"
    
    try:
        # Save uploaded file
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Initialize processing status
        processing_status[request_id] = {
            "status": "processing",
            "message": "Audio received, processing started"
        }
        
        # Process in background
        background_tasks.add_task(process_audio_background, audio_path, request_id)
        
        return {
            "request_id": request_id,
            "status": "processing",
            "message": "Audio processing started"
        }
    
    except Exception as e:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")

async def process_audio_background(audio_path: str, request_id: str):
    """Background task to process audio through the pipeline"""
    try:
        # Process the audio through our pipeline
        result = process_audio_pipeline(audio_path)
        
        # Update processing status
        processing_status[request_id] = {
            "status": "completed",
            "message": "Processing completed",
            "result": result
        }
        
        # Clean up the audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
    except Exception as e:
        processing_status[request_id] = {
            "status": "error",
            "message": f"Error processing audio: {str(e)}"
        }
        if os.path.exists(audio_path):
            os.remove(audio_path)

def process_audio_pipeline(audio_path: str):
    """Process audio through the complete pipeline"""
    from utils.speechToText import translate_audio
    
    # Step 1: Speech to Text (English)
    speech_headers = {"api-subscription-key": SARVAM_AI_API}
    speech_data = {"model": "saaras:v2", "with_diarization": False}
    
    transcript_result = translate_audio(audio_path, speech_headers, speech_data)
    english_text = transcript_result.get("transcript", "")
    
    if not english_text.strip():
        return {"error": "No speech detected or transcription failed"}
    
    # Step 2: Generate solution using Gemini
    solution = findsolution(english_text)
    
    # Step 3: Translate to Bengali
    translate_url = "https://api.sarvam.ai/translate"
    headers = {
        "api-subscription-key": SARVAM_AI_API,
        "Content-Type": "application/json"
    }
    
    chunks = chunk_text(solution, max_length=800)
    translated_texts = []
    
    for chunk in chunks:
        payload = {
            "source_language_code": "en-IN",
            "target_language_code": "bn-IN",
            "speaker_gender": "Male",
            "mode": "formal",
            "model": "mayura:v1",
            "enable_preprocessing": False,
            "input": chunk
        }
        
        response = requests.post(translate_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            translated_text = response.json().get("translated_text", "")
            translated_texts.append(translated_text)
        else:
            translated_texts.append(chunk)  # Fallback to original text
    
    bengali_text = " ".join(translated_texts)
    
    # Step 4: Convert Bengali text to speech
    audio_files = bengali_text_to_speech(bengali_text, request_id=str(uuid.uuid4()))
    
    return {
        "english_text": english_text,
        "solution": solution,
        "bengali_text": bengali_text,
        "audio_files": audio_files
    }

def bengali_text_to_speech(bengali_text, request_id):
    """Convert Bengali text to speech"""
    from utils.textToSpeech import split_text_into_chunks
    
    if not bengali_text.strip():
        return []
    
    client = SarvamAI(api_subscription_key=SARVAM_AI_API)
    chunks = split_text_into_chunks(bengali_text, max_length=300)
    
    audio_files = []
    
    for idx, chunk in enumerate(chunks):
        try:
            response = client.text_to_speech.convert(
                text=chunk,
                target_language_code="bn-IN",
                speaker="anushka",
                enable_preprocessing=True,
            )
            
            output_filename = f"responses/tts_{request_id}_{idx + 1:03d}.wav"
            save(response, output_filename)
            audio_files.append(output_filename)
            
        except Exception as e:
            print(f"Error in TTS for chunk {idx + 1}: {e}")
    
    return audio_files

@app.get("/status/{request_id}")
async def get_status(request_id: str):
    """Get the status of an audio processing request"""
    if request_id not in processing_status:
        raise HTTPException(status_code=404, detail="Request ID not found")
    
    return processing_status[request_id]

@app.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """Get an audio file by filename"""
    file_path = f"responses/{filename}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(file_path, media_type="audio/wav")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
