1. Create a virtual environment.
2. Activate the virtual environment.
3. `pip install -r requirements.txt`
4. `python utils\AudioConverter.py`
5. `python utils\pipeline.py`
6. To start the FastAPI backend: `python app.py`
7. ENJOY! SPEAK IN BENGALI LANGUAGE AND GET YOUR ANSWER IN BENGALI!! MORE LANGUAGES TO BE UPDATED SOON!!

API will be available at: http://localhost:10000 (or the port defined in your .env file)

API Endpoints:

- POST /process-audio/ - Upload audio file for processing
- GET /status/{request_id} - Check processing status
- GET /audio/{filename} - Get generated audio response
