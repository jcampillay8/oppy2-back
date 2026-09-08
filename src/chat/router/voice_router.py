import os
import io
import tempfile
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import speech_recognition as sr
import edge_tts
import pydub

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    lang: str = "es"

@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    Convierte texto a voz usando edge-tts y devuelve un archivo MP3.
    """
    try:
        # Generar audio con edge-tts (voz es-MX o es-ES o es-CL)
        # es-CL-CatalinaNeural es una buena voz
        voice = "es-CL-CatalinaNeural" if request.lang.startswith("es") else "en-US-AriaNeural"
        
        communicate = edge_tts.Communicate(request.text, voice)
        
        audio_fp = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_fp.write(chunk["data"])
        
        audio_fp.seek(0)
        return StreamingResponse(audio_fp, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    """
    Recibe un archivo de audio, lo convierte si es necesario, y lo transcribe con SpeechRecognition.
    """
    try:
        # Guardar archivo subido en temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as tmp_file:
            tmp_file.write(await audio.read())
            tmp_file_path = tmp_file.name

        # Convertir a WAV (SpeechRecognition requiere WAV o AIFF o FLAC)
        # Intentar convertir asumiendo que pydub y ffmpeg están instalados
        # Si el audio ya es WAV, pydub lo manejará
        wav_path = tmp_file_path + ".wav"
        try:
            audio_segment = pydub.AudioSegment.from_file(tmp_file_path)
            audio_segment.export(wav_path, format="wav")
        except Exception as e:
            # Si falla (ej. sin ffmpeg), intentar usar el archivo original si es PCM
            wav_path = tmp_file_path

        # Transcribir usando SpeechRecognition
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="es-CL")
            
        # Limpiar temporales
        try:
            os.remove(tmp_file_path)
            if wav_path != tmp_file_path:
                os.remove(wav_path)
        except:
            pass

        return {"text": text}
    except sr.UnknownValueError:
        # No se pudo entender el audio
        return {"text": ""}
    except sr.RequestError as e:
        # Error en el servicio de Google
        raise HTTPException(status_code=500, detail=f"Error en servicio de reconocimiento de voz: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
