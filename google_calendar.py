import os
import json

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CLIENT_SECRET_FILE = os.path.join(BASE_DIR, "Credentials.json")
SCOPES = ["https://www.googleapis.com/auth/calendar"]
REDIRECT_URI = "http://127.0.0.1:5000/google/callback"


def token_path_por_usuario(usuario_id):
    return os.path.join(BASE_DIR, f"token_google_{usuario_id}.json")


def get_auth_url(usuario_id):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )

    return auth_url, state


def save_token(code, usuario_id):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    flow.fetch_token(code=code)
    creds = flow.credentials

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }

    caminho = token_path_por_usuario(usuario_id)

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)


def get_calendar_service(usuario_id):
    caminho = token_path_por_usuario(usuario_id)

    if not os.path.exists(caminho):
        return None

    with open(caminho, "r", encoding="utf-8") as f:
        token_data = json.load(f)

    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

        with open(caminho, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def criar_evento_google(usuario_id, titulo, descricao, data, hora):
    service = get_calendar_service(usuario_id)
    if not service:
        return None

    evento = {
        "summary": titulo,
        "description": descricao,
        "start": {
            "dateTime": f"{data}T{hora}:00",
            "timeZone": "America/Bahia"
        },
        "end": {
            "dateTime": f"{data}T{hora}:59",
            "timeZone": "America/Bahia"
        }
    }

    criado = service.events().insert(calendarId="primary", body=evento).execute()
    return criado.get("id")