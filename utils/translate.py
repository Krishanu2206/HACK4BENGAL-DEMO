import requests
from sarvamai import SarvamAI
from sarvamai.play import play, save
import os
import dotenv
import time
import threading
from queue import Queue
import re

dotenv.load_dotenv()
SARVAM_AI_API = os.environ.get("SARVAM_AI_API")

def read_file(file_path, lang_name):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            # Read the first 5 lines
            lines = [next(file) for _ in range(5)]
            print(f"=== {lang_name} Text (First Few Lines) ===")
            print("".join(lines))  # Print first few lines

            # Read the remaining content
            remaining_text = file.read()

            # Combine all text
            full_doc = "".join(lines) + remaining_text

            # Count total characters
            total_chars = len(full_doc)
            print(f"\nTotal number of characters in {lang_name} file:", total_chars)

            return full_doc
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return None
    except Exception as e:
        print(f"An error occurred while reading {file_path}: {e}")
        return None
    
english_doc = read_file("", "English")

def chunk_text(text, max_length=1000):
    """Splits text into chunks of at most max_length characters while preserving word boundaries."""
    chunks = []

    while len(text) > max_length:
        split_index = text.rfind(" ", 0, max_length)  # Find the last space within limit
        if split_index == -1:
            split_index = max_length  # No space found, force split at max_length

        chunks.append(text[:split_index].strip())  # Trim spaces before adding
        text = text[split_index:].lstrip()  # Remove leading spaces for the next chunk

    if text:
        chunks.append(text.strip())  # Add the last chunk

    return chunks

# Split the text
english_text_chunks = chunk_text(english_doc)

# Display chunk info
print(f"Total Chunks: {len(english_text_chunks)}")
for i, chunk in enumerate(english_text_chunks[:3], 1):  # Show only first 3 chunks for preview
    print(f"\n=== Chunk {i} (Length: {len(chunk)}) ===\n{chunk}")

# Define API request details
url = "https://api.sarvam.ai/translate"
headers = {
    "api-subscription-key": SARVAM_API_KEY,
    "Content-Type": "application/json"
}

# Send requests for each chunk
translated_texts = []
for idx, chunk in enumerate(english_text_chunks):
    payload = {
        "source_language_code": "en-IN",
        "target_language_code": "bn-IN",
        "speaker_gender": "Male",
        "mode": "classic-colloquial",
        "model": "mayura:v1",
        "enable_preprocessing": False,
        "input": chunk
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        translated_text = response.json().get("translated_text", "Translation not available")
        translated_texts.append(translated_text)
        print(f"\n=== Translated Chunk {idx + 1} ===\n{translated_text}\n")
    else:
        print(f"Error: {response.status_code}, {response.text}")

# Combine all translated chunks
final_translation = "\n".join(translated_texts)
print("\n=== Final Translated Text ===")
print(final_translation)


