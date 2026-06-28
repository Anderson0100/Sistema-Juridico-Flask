from dotenv import load_dotenv
load_dotenv()

import os
from flask import Flask
from flask_wtf.csrf import CSRFProtect

from core.config import (
    DATABASE_URL,
    SECRET_KEY,
    UPLOAD_FOLDER
)
from services.db import db

app = Flask(__name__)
csrf = CSRFProtect()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não foi carregado do .env")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY nao foi carregado do .env")

SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

app.config["SECRET_KEY"] = SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)
csrf.init_app(app)

from models import *

from whatsapp.helpers import inicializar_estado_whatsapp
inicializar_estado_whatsapp()

from routes.auth_routes import auth_bp
app.register_blueprint(auth_bp)

from routes.admin_routes import admin_bp
app.register_blueprint(admin_bp)

from routes.advogado_routes import adv_bp
app.register_blueprint(adv_bp)

from routes.cliente_routes import *
from routes.processo_routes import *
from routes.aux_routes import *
from whatsapp.routes import *

from jobs.scheduler import iniciar_scheduler

if ENABLE_SCHEDULER:
    iniciar_scheduler(app)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=FLASK_DEBUG, use_reloader=False)
