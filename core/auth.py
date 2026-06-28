from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(tipo=None):
    def decorator(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if "usuario_id" not in session:
                return redirect(url_for("auth.login"))

            if tipo and session.get("usuario_tipo") != tipo:
                flash("Acesso negado", "danger")
                return redirect(url_for("auth.login"))

            return f(*args, **kwargs)

        return wrap

    return decorator


def pode_editar_processo(processo):
    return (
        session.get("usuario_tipo") == "admin" or
        (
            session.get("usuario_tipo") == "advogado"
            and processo.advogado_id == session.get("usuario_id")
        )
    )


def pode_ver_processo(processo):
    tipo = session.get("usuario_tipo")
    usuario_id = session.get("usuario_id")

    return (
        tipo == "admin" or
        (tipo == "advogado" and processo.advogado_id == usuario_id) or
        (tipo == "cliente" and processo.cliente_id == usuario_id)
    )
