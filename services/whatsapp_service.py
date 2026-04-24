import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("EVOLUTION_API_URL")
API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE = os.getenv("EVOLUTION_INSTANCE")


def enviar_mensagem(numero, mensagem):
    url = f"{API_URL}/message/sendText/{INSTANCE}"

    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "number": numero,
        "text": mensagem
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=15)
        print("WhatsApp status:", response.status_code)
        return response.json()
    except Exception as e:
        print("Erro ao enviar WhatsApp:", e)
        return None