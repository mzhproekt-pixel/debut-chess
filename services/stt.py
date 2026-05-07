import os
import speech_recognition as sr
from pydub import AudioSegment


async def transcribe(audio_path: str) -> str:
    wav_path = audio_path.replace(".ogg", ".wav")
    AudioSegment.from_ogg(audio_path).export(wav_path, format="wav")

    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_path) as source:
        audio = recognizer.record(source)
    os.remove(wav_path)

    try:
        return recognizer.recognize_google(audio, language="ru-RU")
    except sr.UnknownValueError:
        return "[не удалось распознать речь]"
    except sr.RequestError as e:
        return f"[ошибка распознавания: {e}]"
