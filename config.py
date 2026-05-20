from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "files"
DB_DIR = BASE_DIR / "database"
DB_PATH = DB_DIR / "files.db"

# Категории файлов. Ключ используется в коде, название показывается пользователю.
CATEGORIES = {
    "study": "Учёба",
    "documents": "Документы",
    "photos": "Фото",
    "code": "Код",
    "reports": "Отчёты",
    "other": "Другое",
}

MAX_FILE_SIZE_MB = 50


def get_bot_token() -> str:
    """Читает токен Telegram-бота из файла .env."""
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Не найден BOT_TOKEN. Создайте файл .env по примеру .env.example "
            "и вставьте туда токен от BotFather."
        )
    return token
