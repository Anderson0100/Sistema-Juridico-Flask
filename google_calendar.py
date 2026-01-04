import os
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

REDIRECT_URI = "http://127.0.0.1:5000/google/callback"


def get_auth_url():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )

    return auth_url


def save_token(code):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    flow.fetch_token(code=code)

    creds = flow.credentials

    with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())


def get_calendar_service():
    if not os.path.exists(TOKEN_FILE):
        return None

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build("calendar", "v3", credentials=creds)

# 📅 Cria evento na agenda
def criar_evento_google(titulo, descricao, data, hora):
    service = get_calendar_service()

    if not service:
        return None

    evento = {
        "summary": titulo,
        "description": descricao,
        "start": {
            "dateTime": f"{data}T{hora}:00",
            "timeZone": "America/Sao_Paulo"
        },
        "end": {
            "dateTime": f"{data}T{hora}:00",
            "timeZone": "America/Sao_Paulo"
        }
    }

    event = service.events().insert(calendarId="primary", body=evento).execute()
    return event["id"]
