import pyaudio
import wave
import numpy as np
import os
import time
import threading

# Configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
OUTPUT_DIR = "audio_chunks"
THRESHOLD = 500
SILENCE_CHUNKS = 50
MIN_RECORDING_TIME = 2  # Minimum recording time in seconds

os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_chunk(frames, filename):
    """Save audio frames to a WAV file"""
    try:
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
        print(f"Saved {filename}")
        return True
    except Exception as e:
        print(f"Error saving {filename}: {e}")
        return False

def continuous_recording():
    """Continuously record and save audio chunks"""
    global p, stream
    
    print("Starting continuous recording...")
    frames = []
    chunk_counter = 0
    file_counter = 0
    silent_chunks = 0
    recording_started = False
    
    try:
        while True:
            data = stream.read(CHUNK)
            audio_data = np.frombuffer(data, dtype=np.int16)
            amplitude = np.abs(audio_data).mean()
            
            # Check if we have sound
            if amplitude > THRESHOLD:
                if not recording_started:
                    recording_started = True
                    print("Sound detected, starting recording...")
                frames.append(data)
                silent_chunks = 0
                chunk_counter += 1
            else:
                if recording_started:
                    silent_chunks += 1
                    frames.append(data)  # Keep recording during brief silences
                    chunk_counter += 1
            
            # Save when we have enough silence or enough audio
            min_chunks = int(RATE / CHUNK * MIN_RECORDING_TIME)
            max_chunks = int(RATE / CHUNK * 10)  # Max 10 seconds per chunk
            
            if recording_started and (silent_chunks > SILENCE_CHUNKS or chunk_counter >= max_chunks):
                if chunk_counter >= min_chunks:  # Only save if we have minimum recording
                    timestamp = int(time.time())
                    filename = f"{OUTPUT_DIR}/chunk_{timestamp}_{file_counter}.wav"
                    
                    if save_chunk(frames, filename):
                        file_counter += 1
                
                # Reset for next recording
                frames = []
                chunk_counter = 0
                silent_chunks = 0
                recording_started = False
                
                if silent_chunks > SILENCE_CHUNKS:
                    print("Waiting for next sound...")
            
            time.sleep(0.001)  # Small delay to prevent excessive CPU usage
            
    except KeyboardInterrupt:
        print("\nStopping recording...")
    except Exception as e:
        print(f"Recording error: {e}")
    finally:
        # Save any remaining frames
        if frames and chunk_counter >= min_chunks:
            timestamp = int(time.time())
            filename = f"{OUTPUT_DIR}/chunk_{timestamp}_{file_counter}_final.wav"
            save_chunk(frames, filename)

def start_recording():
    """Initialize and start the recording process"""
    global p, stream
    
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    
    try:
        continuous_recording()
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    start_recording()

