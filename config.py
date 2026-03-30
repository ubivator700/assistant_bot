import os
import sys
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = ["TELEGRAM_TOKEN", "ANTHROPIC_API_KEY", "MYSQL_PASSWORD"]


def _get_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"ERROR: обязательная переменная окружения {name} не задана", file=sys.stderr)
        sys.exit(1)
    return value


# Telegram
TELEGRAM_TOKEN: str = _get_required("TELEGRAM_TOKEN")
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))

# Anthropic
ANTHROPIC_API_KEY: str = _get_required("ANTHROPIC_API_KEY")

# MySQL
MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER: str = os.getenv("MYSQL_USER", "assistant")
MYSQL_PASSWORD: str = _get_required("MYSQL_PASSWORD")
MYSQL_DB: str = os.getenv("MYSQL_DB", "assistant_bot")

DATABASE_URL: str = (
    f"mysql+aiomysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
)

# Timezone
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Vienna")

# Bot mode
BOT_MODE: str = os.getenv("BOT_MODE", "polling")  # polling | webhook
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
