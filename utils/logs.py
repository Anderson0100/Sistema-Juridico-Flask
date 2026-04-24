from flask import session
from services.db import db
from models import SistemaLog


def log_sistema(acao):
    if "usuario_id" in session:
        db.session.add(SistemaLog(
            usuario_id=session["usuario_id"],
            usuario_nome=session["usuario_nome"],
            acao=acao
        ))
        db.session.commit()