import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
DB_PATH = os.getenv("DB_PATH", "teachers.db")
PHOTOS_DIR = os.getenv("PHOTOS_DIR", "photos")
