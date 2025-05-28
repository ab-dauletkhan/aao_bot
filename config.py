import os
from dotenv import load_dotenv

load_dotenv()

# Telegram and OpenAI credentials
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODERATOR_CHAT_ID = os.getenv("MODERATOR_CHAT_ID")
ADVISOR_USER_IDS_STR = os.getenv("ADVISOR_USER_IDS", "")
ADVISOR_USER_IDS = (
    set(map(int, ADVISOR_USER_IDS_STR.split(","))) if ADVISOR_USER_IDS_STR else set()
)

# Webhook settings
WEBHOOK_LISTEN_IP = os.getenv("WEBHOOK_LISTEN_IP", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8443")))
WEBHOOK_URL_PATH = os.getenv("WEBHOOK_URL_PATH", "")
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN", "")

# Special markers
NOT_A_QUESTION_MARKER = "[NOT_A_QUESTION]"
CANNOT_ANSWER_MARKER = "[CANNOT_ANSWER]"

# Load FAQ content
FAQ_CONTENT = ""
try:
    with open("faq.md", "r", encoding="utf-8") as f:
        FAQ_CONTENT = f.read()
except FileNotFoundError:
    FAQ_CONTENT = ""
except Exception:
    FAQ_CONTENT = ""
