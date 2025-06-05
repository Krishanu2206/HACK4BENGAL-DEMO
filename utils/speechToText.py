import requests
import io
import dotenv
import os
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from queue import Queue
from pydub import AudioSegment

dotenv.load_dotenv()
SARVAM_AI_API = os.environ.get("SARVAM_AI_API")

# API configuration
api_url = "https://api.sarvam.ai/speech-to-text-translate"  # Add your API URL
headers = {
    "api-subscription-key": SARVAM_AI_API
}

data = {
    "model": "saaras:v2",
    "with_diarization": False
}

# Queue to store files for processing
file_queue = Queue()
processed_files = set()

class AudioFileHandler(FileSystemEventHandler):
    """Handler for monitoring new audio files"""
    
    def on_created(self, event):
        if event.is_file and event.src_path.endswith('.wav'):
            print(f"New audio file detected: {event.src_path}")
            # Wait a bit to ensure file is completely written
            time.sleep(0.5)
            if os.path.getsize(event.src_path) > 0:  # Check if file has content
                file_queue.put(event.src_path)

def split_audio(audio_path, chunk_duration_ms):
    """
    Splits an audio file into smaller chunks of specified duration.
    """
    try:
        audio = AudioSegment.from_file(audio_path)
        chunks = []
        if len(audio) > chunk_duration_ms:
            for i in range(0, len(audio), chunk_duration_ms):
                chunks.append(audio[i:i + chunk_duration_ms])
        else:
            chunks.append(audio)
        return chunks
    except Exception as e:
        print(f"Error splitting audio {audio_path}: {e}")
        return []

def process_audio_chunk(chunk, chunk_idx, headers, data):
    """
    Process a single audio chunk and return transcript
    """
    chunk_buffer = io.BytesIO()
    try:
        chunk.export(chunk_buffer, format="wav")
        chunk_buffer.seek(0)
        
        files = {'file': ('audiofile.wav', chunk_buffer, 'audio/wav')}
        
        response = requests.post(api_url, headers=headers, files=files, data=data)
        if response.status_code in [200, 201]:
            print(f"Chunk {chunk_idx} processed successfully!")
            response_data = response.json()
            return response_data.get("transcript", "")
        else:
            print(f"Chunk {chunk_idx} failed with status: {response.status_code}")
            print("Response:", response.text)
            return ""
    except Exception as e:
        print(f"Error processing chunk {chunk_idx}: {e}")
        return ""
    finally:
        chunk_buffer.close()

def translate_audio(audio_file_path, headers, data, chunk_duration_ms=5*60*1000):
    """
    Translates audio into text with optional diarization and timestamps.
    """
    print(f"Processing audio file: {audio_file_path}")
    
    # Check if file exists and has content
    if not os.path.exists(audio_file_path) or os.path.getsize(audio_file_path) == 0:
        print(f"File {audio_file_path} does not exist or is empty")
        return {"transcript": "", "language": ""}
    
    chunks = split_audio(audio_file_path, chunk_duration_ms)
    if not chunks:
        return {"transcript": "", "language": ""}
    
    transcripts = []
    language = ""
    
    for idx, chunk in enumerate(chunks):
        transcript = process_audio_chunk(chunk, idx, headers, data)
        if transcript:
            transcripts.append(transcript)
    
    collated_transcript = " ".join(transcripts)
    
    # Clean up processed file
    try:
        os.remove(audio_file_path)
        print(f"Cleaned up processed file: {audio_file_path}")
    except Exception as e:
        print(f"Error cleaning up file {audio_file_path}: {e}")
    
    result = {
        "transcript": collated_transcript,
        "language": language,
        "file": audio_file_path
    }
    
    return result

def audio_processor_worker():
    """
    Worker thread that continuously processes audio files from the queue
    """
    print("Audio processor worker started...")
    
    while True:
        try:
            # Get file from queue (blocks until available)
            audio_file_path = file_queue.get(timeout=1)
            
            # Skip if already processed
            if audio_file_path in processed_files:
                file_queue.task_done()
                continue
                
            # Process the audio file
            result = translate_audio(audio_file_path, headers, data)
            
            if result["transcript"]:
                print(f"\n=== TRANSCRIPT ===")
                print(f"File: {result['file']}")
                print(f"Text: {result['transcript']}")
                print(f"==================\n")
                
                # Save transcript to file
                transcript_file = audio_file_path.replace('.wav', '_transcript.txt')
                with open(transcript_file, 'w', encoding='utf-8') as f:
                    f.write(result['transcript'])
            
            # Mark as processed
            processed_files.add(audio_file_path)
            file_queue.task_done()
            
        except Exception as e:
            if "Empty" not in str(e):  # Ignore queue timeout
                print(f"Error in audio processor: {e}")
            time.sleep(0.1)

def start_continuous_processing(audio_dir="audio_chunks"):
    """
    Start continuous monitoring and processing of audio files
    """
    # Create directory if it doesn't exist
    os.makedirs(audio_dir, exist_ok=True)
    
    # Process any existing files first
    existing_files = [f for f in os.listdir(audio_dir) if f.endswith('.wav')]
    for filename in existing_files:
        file_path = os.path.join(audio_dir, filename)
        if file_path not in processed_files:
            file_queue.put(file_path)
    
    # Start the processor worker thread
    processor_thread = threading.Thread(target=audio_processor_worker, daemon=True)
    processor_thread.start()
    
    # Set up file system watcher
    event_handler = AudioFileHandler()
    observer = Observer()
    observer.schedule(event_handler, audio_dir, recursive=False)
    observer.start()
    
    print(f"Started monitoring directory: {audio_dir}")
    print("Waiting for audio files...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping continuous processing...")
        observer.stop()
        observer.join()

if __name__ == "__main__":
    # Start continuous processing
    start_continuous_processing()

