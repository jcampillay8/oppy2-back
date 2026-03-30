# src/ai_management/audio_client.py
import os
import base64
import json
import time
import logging
from io import BytesIO
from google.cloud import texttospeech
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

# Configuración de Voces Standard
STANDARD_VOICES = {
    "us_female": {
        "language_code": "en-US",
        "voice_name": "en-US-Standard-C", # Voz femenina estándar
        "ssml_gender": texttospeech.SsmlVoiceGender.FEMALE
    },
    "us_male": {
        "language_code": "en-US",
        "voice_name": "en-US-Standard-B", # Voz masculina estándar
        "ssml_gender": texttospeech.SsmlVoiceGender.MALE
    },
    "uk_male": {
        "language_code": "en-GB",
        "voice_name": "en-GB-Standard-B",
        "ssml_gender": texttospeech.SsmlVoiceGender.MALE
    },
    "uk_female": {
        "language_code": "en-GB",
        "voice_name": "en-GB-Standard-A",
        "ssml_gender": texttospeech.SsmlVoiceGender.FEMALE
    }
}

class TTSClient:
    def __init__(self):
        self.client = self._init_client()

    def _init_client(self):
        creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64")
        if creds_b64:
            try:
                info = json.loads(base64.b64decode(creds_b64).decode('utf-8'))
                return texttospeech.TextToSpeechClient(credentials=Credentials.from_service_account_info(info))
            except Exception as e:
                logger.error(f"Error initializing TTS with B64: {e}")
        return texttospeech.TextToSpeechClient() # Fallback a ADC

    async def synthesize(self, text: str, voice_key: str = "us_female") -> bytes:
        # 1. Aseguramos que la llave existe, si no, usamos us_female
        voice_cfg = STANDARD_VOICES.get(voice_key, STANDARD_VOICES["us_female"])
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # 2. Corregimos los nombres de las llaves para que coincidan con el diccionario
        voice = texttospeech.VoiceSelectionParams(
            language_code=voice_cfg["language_code"],
            name=voice_cfg["voice_name"],
            ssml_gender=voice_cfg["ssml_gender"]
        )
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

        # Ejecución síncrona de la SDK de Google
        response = self.client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        return response.audio_content

tts_client = TTSClient()