import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

CLAUDE_MODEL = "claude-sonnet-4-6"
WHISPER_MODEL = "whisper-1"

MAX_MEMORY_MESSAGES = 20
MAX_SEARCH_RESULTS = 5

DB_PATH = os.path.join(os.path.dirname(__file__), "jarvis.db")
VOICE_DIR = os.path.join(os.path.dirname(__file__), "tmp_voice")
os.makedirs(VOICE_DIR, exist_ok=True)
