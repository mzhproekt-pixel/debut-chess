import os
import uuid
from gtts import gTTS
from config import VOICE_DIR


def text_to_speech(text: str, lang: str = "ru") -> str:
    path = os.path.join(VOICE_DIR, f"{uuid.uuid4()}.ogg")
    tts = gTTS(text=text, lang=lang, slow=False)
    mp3_path = path.replace(".ogg", ".mp3")
    tts.save(mp3_path)
    os.system(f"ffmpeg -y -i {mp3_path} -c:a libopus {path} -loglevel quiet")
    os.remove(mp3_path)
    return path
