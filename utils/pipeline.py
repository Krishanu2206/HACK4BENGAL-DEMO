import requests
import io
import dotenv
import os
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from queue import Queue, Empty
from pydub import AudioSegment
import glob
import re
from sarvamai import SarvamAI
from sarvamai.play import play, save
from utils.LLM import findsolution

dotenv.load_dotenv()
SARVAM_AI_API = os.environ.get("SARVAM_AI_API")

# Global variables
is_running = True
file_queue = Queue()
processed_files = set()

class AudioFileHandler(FileSystemEventHandler):
    """Handler for monitoring new audio files"""
    
    def on_created(self, event):
        if event.is_file and event.src_path.endswith('.wav'):
            self._process_new_file(event.src_path)
    
    def on_modified(self, event):
        if event.is_file and event.src_path.endswith('.wav'):
            self._process_new_file(event.src_path)
    
    def _process_new_file(self, file_path):
        """Process a new or modified audio file"""
        print(f"🎵 Audio file detected: {file_path}")
        self._wait_for_file_completion(file_path)
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            if file_path not in processed_files:
                print(f"📋 Adding to processing queue: {os.path.basename(file_path)}")
                file_queue.put(file_path)
    
    def _wait_for_file_completion(self, file_path, max_wait=3):
        """Wait for file to be completely written"""
        start_time = time.time()
        last_size = 0
        
        while time.time() - start_time < max_wait:
            try:
                current_size = os.path.getsize(file_path)
                if current_size == last_size and current_size > 0:
                    time.sleep(0.1)
                    break
                last_size = current_size
                time.sleep(0.1)
            except (OSError, FileNotFoundError):
                time.sleep(0.1)

def process_audio_chunk(chunk, chunk_idx):
    """Process a single audio chunk and return transcript"""
    chunk_buffer = io.BytesIO()
    try:
        chunk.export(chunk_buffer, format="wav")
        chunk_buffer.seek(0)
        
        files = {'file': ('audiofile.wav', chunk_buffer, 'audio/wav')}
        
        response = requests.post(speech_to_text_url, headers={
            "api-subscription-key": SARVAM_AI_API
        }, files=files, data=speech_data)
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            transcript = response_data.get("transcript", "")
            return transcript
        else:
            print(f"❌ STT failed for chunk {chunk_idx}: {response.status_code}")
            return ""
    except Exception as e:
        print(f"❌ Error in STT chunk {chunk_idx}: {e}")
        return ""
    finally:
        chunk_buffer.close()

def speech_to_text(audio_file_path, chunk_duration_ms=30*1000):
    """Convert speech to text"""
    print(f"🗣️ Converting speech to text: {os.path.basename(audio_file_path)}")
    
    if not os.path.exists(audio_file_path) or os.path.getsize(audio_file_path) == 0:
        return ""
    
    try:
        audio = AudioSegment.from_file(audio_file_path)
        chunks = []
        if len(audio) > chunk_duration_ms:
            for i in range(0, len(audio), chunk_duration_ms):
                chunks.append(audio[i:i + chunk_duration_ms])
        else:
            chunks.append(audio)
        
        transcripts = []
        for idx, chunk in enumerate(chunks):
            transcript = process_audio_chunk(chunk, idx)
            if transcript.strip():
                transcripts.append(transcript.strip())
        
        return " ".join(transcripts)
    except Exception as e:
        print(f"❌ Error in speech to text: {e}")
        return ""

def chunk_text(text, max_length=800):
    """Splits text into chunks while preserving word boundaries"""
    if len(text) <= max_length:
        return [text.strip()]
    
    chunks = []
    while len(text) > max_length:
        split_index = text.rfind(" ", 0, max_length)
        if split_index == -1:
            split_index = max_length
        
        chunks.append(text[:split_index].strip())
        text = text[split_index:].lstrip()
    
    if text:
        chunks.append(text.strip())
    
    return chunks

def translate_text(english_text):
    """Translate English text to Bengali"""
    if not english_text.strip():
        return ""
    
    print(f"🔄 Translating text: {english_text[:50]}...")
    
    try:
        chunks = chunk_text(english_text)
        translated_texts = []
        
        for idx, chunk in enumerate(chunks):
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
                print(f"✅ Translated chunk {idx + 1}")
            else:
                print(f"❌ Translation failed for chunk {idx + 1}: {response.status_code}")
                translated_texts.append(chunk)  # Fallback to original text
        
        return " ".join(translated_texts)
    except Exception as e:
        print(f"❌ Error in translation: {e}")
        return english_text  # Return original text on error

def split_text_for_tts(text, max_length=400):
    """Split text into smaller chunks for TTS processing"""
    if len(text) <= max_length:
        return [text.strip()]
    
    chunks = []
    sentences = re.split(r'[।.!?]+', text)
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        if len(current_chunk) + len(sentence) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                # Split long sentence by words
                words = sentence.split()
                temp_chunk = ""
                for word in words:
                    if len(temp_chunk) + len(word) + 1 > max_length:
                        if temp_chunk:
                            chunks.append(temp_chunk.strip())
                            temp_chunk = word
                        else:
                            chunks.append(word[:max_length])
                            temp_chunk = word[max_length:]
                    else:
                        temp_chunk += " " + word if temp_chunk else word
                if temp_chunk:
                    current_chunk = temp_chunk
        else:
            current_chunk += " " + sentence if current_chunk else sentence
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def text_to_speech(bengali_text):
    """Convert Bengali text to speech"""
    if not bengali_text.strip():
        return []
    
    print(f"🎤 Converting text to speech: {bengali_text[:50]}...")
    
    try:
        client = SarvamAI(api_subscription_key=SARVAM_AI_API)
        chunks = split_text_for_tts(bengali_text, max_length=300)
        
        print(f"📝 Text split into {len(chunks)} TTS chunks")
        
        result_queue = Queue()
        
        def tts_worker(chunk, index):
            try:
                response = client.text_to_speech.convert(
                    text=chunk,
                    target_language_code="bn-IN",
                    speaker="anushka",
                    enable_preprocessing=True,
                )
                
                output_filename = f"tts_output_{int(time.time())}_{index + 1:03d}.wav"
                save(response, output_filename)
                result_queue.put((index, response, output_filename))
                print(f"✅ TTS chunk {index + 1} completed")
            except Exception as e:
                print(f"❌ TTS error for chunk {index + 1}: {e}")
                result_queue.put((index, None, None))
        
        # Process TTS chunks in batches
        max_threads = 3
        for i in range(0, len(chunks), max_threads):
            batch = chunks[i:i + max_threads]
            threads = []
            
            for j, chunk in enumerate(batch):
                thread = threading.Thread(target=tts_worker, args=(chunk, i + j))
                thread.start()
                threads.append(thread)
            
            for thread in threads:
                thread.join()
        
        # Collect and sort results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())
        
        results.sort(key=lambda x: x[0])
        
        # Play audio files in order
        print("🔊 Playing Bengali audio...")
        for index, response, filename in results:
            if response:
                try:
                    play(response)
                    time.sleep(0.3)  # Brief pause between chunks
                except Exception as e:
                    print(f"❌ Error playing chunk {index + 1}: {e}")
        
        return [filename for _, _, filename in results if filename]
        
    except Exception as e:
        print(f"❌ Error in text to speech: {e}")
        return []

def process_pipeline(audio_file_path):
    """Complete pipeline: Speech -> Text -> Translation -> Speech"""
    start_time = time.time()
    print(f"\n🚀 Starting pipeline for: {os.path.basename(audio_file_path)}")
    
    try:
        # Step 1: Speech to Text (English)
        english_text = speech_to_text(audio_file_path)
        if not english_text.strip():
            print("❌ No speech detected or transcription failed")
            return
        
        print(f"📝 English transcript: {english_text}")

        solution = findsolution(english_text)
        print(f"💡 Solution found: {solution}")
        
        # Step 2: Translate to Bengali
        bengali_text = translate_text(solution)
        if not bengali_text.strip():
            print("❌ Translation failed")
            return
        
        print(f"🔄 Bengali translation: {bengali_text}")
        
        # Step 3: Text to Speech (Bengali)
        audio_files = text_to_speech(bengali_text)
        
        processing_time = time.time() - start_time
        print(f"✅ Pipeline completed in {processing_time:.2f} seconds")
        
        # Save results
        base_name = os.path.splitext(audio_file_path)[0]
        
        # Save English transcript
        with open(f"{base_name}_english.txt", 'w', encoding='utf-8') as f:
            f.write(f"English Transcript:\n{english_text}\n")
        
        # Save Bengali translation
        with open(f"{base_name}_bengali.txt", 'w', encoding='utf-8') as f:
            f.write(f"Bengali Translation:\n{bengali_text}\n")
        
        print(f"💾 Results saved")
        
    except Exception as e:
        print(f"❌ Pipeline error: {e}")

def pipeline_worker():
    """Worker thread that processes files through the complete pipeline"""
    global is_running
    print("🚀 Pipeline worker started...")
    
    while is_running:
        try:
            audio_file_path = file_queue.get(timeout=0.5)
            
            if audio_file_path in processed_files:
                file_queue.task_done()
                continue
            
            # Process through complete pipeline
            process_pipeline(audio_file_path)
            
            # Mark as processed
            processed_files.add(audio_file_path)
            
            # Clean up original audio file after processing
            cleanup_thread = threading.Thread(
                target=delayed_cleanup, 
                args=(audio_file_path, 10), 
                daemon=True
            )
            cleanup_thread.start()
            
            file_queue.task_done()
            
        except Empty:
            continue
        except Exception as e:
            print(f"❌ Pipeline worker error: {e}")
            time.sleep(0.1)

def delayed_cleanup(file_path, delay_seconds):
    """Clean up file after delay"""
    time.sleep(delay_seconds)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ Cleaned up: {os.path.basename(file_path)}")
    except Exception as e:
        print(f"❌ Cleanup error: {e}")

def periodic_scan(audio_dir):
    """Periodically scan for new files"""
    global is_running
    
    while is_running:
        try:
            pattern = os.path.join(audio_dir, "*.wav")
            files = glob.glob(pattern)
            files.sort(key=os.path.getmtime, reverse=True)
            
            for file_path in files[:2]:  # Check last 2 files
                if file_path not in processed_files and os.path.getsize(file_path) > 0:
                    if time.time() - os.path.getmtime(file_path) > 1:
                        file_queue.put(file_path)
            
            time.sleep(3)
            
        except Exception as e:
            print(f"❌ Scan error: {e}")
            time.sleep(5)

def start_pipeline(audio_dir="audio_chunks"):
    """Start the complete voice translation pipeline"""
    global is_running
    
    os.makedirs(audio_dir, exist_ok=True)
    
    print("🎯 Voice Translation Pipeline Started")
    print(f"📁 Monitoring: {os.path.abspath(audio_dir)}")
    print("🎤 Record English -> 🔄 Translate -> 🗣️ Bengali Audio")
    
    # Start pipeline worker
    worker_thread = threading.Thread(target=pipeline_worker, daemon=True)
    worker_thread.start()
    
    # Start periodic scanner
    scanner_thread = threading.Thread(target=periodic_scan, args=(audio_dir,), daemon=True)
    scanner_thread.start()
    
    # Set up file watcher
    event_handler = AudioFileHandler()
    observer = Observer()
    observer.schedule(event_handler, audio_dir, recursive=False)
    observer.start()
    
    print("✅ Pipeline ready! Start recording with AudioConverter.py")
    
    try:
        while True:
            time.sleep(1)
            if int(time.time()) % 15 == 0:
                queue_size = file_queue.qsize()
                if queue_size > 0:
                    print(f"📊 Queue: {queue_size}, Processed: {len(processed_files)}")
    except KeyboardInterrupt:
        print("\n🛑 Stopping pipeline...")
        is_running = False
        observer.stop()
        observer.join()