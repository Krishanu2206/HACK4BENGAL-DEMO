import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

# Configure the Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def findsolution(text):
    """Generate responses about Bengali culture using Google's Gemini model"""
    try:
        # Configure the model
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 1024,
        }
        
        # Initialize Gemini model
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config
        )
        
        # Create prompt with system and user content
        prompt = f"""
        System: You are a knowledgeable assistant specializing in Bengali culture, heritage, literature, and traditions.
        Please provide informative and engaging responses about Bengali history, arts, cuisine, festivals, language, 
        or any cultural aspects. Ensure your responses are respectful, authentic, and celebrate the rich Bengali heritage.
        Keep responses clear, engaging, short, and to the point.
        
        User: {text}
        """
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Return the response text
        return response.text
    except Exception as e:
        print(f"Error in Gemini API call: {e}")
        return f"Sorry, I couldn't process your request due to an error: {str(e)}"