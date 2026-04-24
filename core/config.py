import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"pdf"}

MODO_HUMANO_FILE = os.path.join(BASE_DIR, "modo_humano.json")
FILA_ATENDIMENTO_FILE = os.path.join(BASE_DIR, "fila_atendimento.json")

TTL_SESSAO = 60 * 30
TTL_EVENTO = 60 * 10

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")