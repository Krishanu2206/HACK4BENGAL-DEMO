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

def split_text_into_chunks(text, max_length=500):
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

def text_to_speech_chunk(client, text_chunk, chunk_index, target_language="bn-IN", speaker="anushka"):
    """Convert a single text chunk to speech"""
    try:
        print(f"🎤 Processing chunk {chunk_index + 1}: {text_chunk[:50]}...")
        
        response = client.text_to_speech.convert(
            text=text_chunk,
            target_language_code=target_language,
            speaker=speaker,
            enable_preprocessing=True,
        )
        
        output_filename = f"output_chunk_{chunk_index + 1:03d}.wav"
        save(response, output_filename)
        print(f"✅ Saved: {output_filename}")
        
        return response, output_filename
        
    except Exception as e:
        print(f"❌ Error processing chunk {chunk_index + 1}: {e}")
        return None, None

def threaded_text_to_speech(text, max_chunk_length=300, target_language="bn-IN", speaker="anushka", max_threads=3):
    """Process text to speech using multiple threads for faster processing"""
    client = SarvamAI(api_subscription_key=SARVAM_AI_API)
    chunks = split_text_into_chunks(text, max_chunk_length)
    
    print(f"📝 Text split into {len(chunks)} chunks")
    print("🚀 Starting threaded processing...")
    
    result_queue = Queue()
    
    def worker(chunk, index):
        response, filename = text_to_speech_chunk(client, chunk, index, target_language, speaker)
        result_queue.put((index, response, filename))
    
    # Process chunks in batches to avoid API rate limits
    for i in range(0, len(chunks), max_threads):
        batch = chunks[i:i + max_threads]
        threads = []
        
        # Start threads for current batch
        for j, chunk in enumerate(batch):
            thread = threading.Thread(target=worker, args=(chunk, i + j))
            thread.start()
            threads.append(thread)
        
        # Wait for batch to complete
        for thread in threads:
            thread.join()
    
    # Collect and sort results
    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    
    results.sort(key=lambda x: x[0])
    
    print(f"\n✅ Threaded processing completed!")
    
    # Play audio files in order
    for index, response, filename in results:
        if response:
            print(f"🔊 Playing chunk {index + 1}...")
            try:
                play(response)
                time.sleep(0.5)
            except Exception as e:
                print(f"❌ Error playing chunk {index + 1}: {e}")
    
    return [filename for _, _, filename in results if filename]

# Example usage
if __name__ == "__main__":
    text = """
    আমি এখানে সহনীয় ও সম্মানজনক ভাষা ব্যবহার করতে উৎসাহ দিই। আপনি যদি মজার বা কৌতুকপূর্ণ বাংলা টেক্সট চান, আমি সেটা দিতে পারি。
    
    দেবজিত এমন এক বন্ধু, যাকে ছাড়া ঝামেলা অসম্পূর্ণ。
    ওর বুদ্ধি এমন, চা বানাতে গেলেও ইউটিউব দেখে!
    দেবজিত আর সমস্যার মধ্যে পার্থক্য খুঁজে পাওয়া মুশকিল!
    
    আপনি যদি আরও মজার বা নির্দিষ্ট প্রসঙ্গের বাংলা টেক্সট চান, জানাতে পারেন!

    আমি এখানে সহনীয় ও সম্মানজনক ভাষা ব্যবহার করতে উৎসাহ দিই। আপনি যদি মজার বা কৌতুকপূর্ণ বাংলা টেক্সট চান, আমি সেটা দিতে পারি。
    
    দেবজিত এমন এক বন্ধু, যাকে ছাড়া ঝামেলা অসম্পূর্ণ。
    ওর বুদ্ধি এমন, চা বানাতে গেলেও ইউটিউব দেখে!
    দেবজিত আর সমস্যার মধ্যে পার্থক্য খুঁজে পাওয়া মুশকিল!
    
    আপনি যদি আরও মজার বা নির্দিষ্ট প্রসঙ্গের বাংলা টেক্সট চান, জানাতে পারেন!

    আমি এখানে সহনীয় ও সম্মানজনক ভাষা ব্যবহার করতে উৎসাহ দিই। আপনি যদি মজার বা কৌতুকপূর্ণ বাংলা টেক্সট চান, আমি সেটা দিতে পারি。
    
    দেবজিত এমন এক বন্ধু, যাকে ছাড়া ঝামেলা অসম্পূর্ণ。
    ওর বুদ্ধি এমন, চা বানাতে গেলেও ইউটিউব দেখে!
    দেবজিত আর সমস্যার মধ্যে পার্থক্য খুঁজে পাওয়া মুশকিল!
    
    আপনি যদি আরও মজার বা নির্দিষ্ট প্রসঙ্গের বাংলা টেক্সট চান, জানাতে পারেন!
    """
    
    threaded_text_to_speech(text, max_chunk_length=200, max_threads=3)

