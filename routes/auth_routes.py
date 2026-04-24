import re

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

from core.auth import login_required
from google_calendar import get_auth_url, save_token
from models import Usuario


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        tipo = request.form["tipo"]

        if tipo in ["admin", "advogado"]:
            user = Usuario.query.filter_by(
                email=request.form["email"],
                tipo=tipo
            ).first()

            if user and check_password_hash(user.senha, request.form["senha"]):
                if not user.ativo:
                    flash("Conta desativada pelo administrador", "danger")
                    return redirect(url_for("auth.login"))

                session.update({
                    "usuario_id": user.id,
                    "usuario_nome": user.nome,
                    "usuario_tipo": user.tipo
                })

                if user.tipo == "admin":
                    return redirect(url_for("admin.painel_admin"))

                return redirect(url_for("adv.painel_advogado"))

            flash("Login inválido", "danger")

        elif tipo == "cliente":
            cpf = re.sub(r"\D", "", request.form["cpf"])

            user = Usuario.query.filter_by(
                cpf=cpf,
                data_nascimento=request.form["data_nascimento"],
                tipo="cliente"
            ).first()

            if user:
                session.update({
                    "usuario_id": user.id,
                    "usuario_nome": user.nome,
                    "usuario_tipo": user.tipo
                })

                return redirect(url_for("cliente.painel_cliente"))

            flash("Dados inválidos", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/google/login")
@login_required("advogado")
def google_login():
    usuario_id = session["usuario_id"]
    auth_url, state = get_auth_url(usuario_id)
    session["google_oauth_state"] = state
    return redirect(auth_url)


@auth_bp.route("/google/callback")
@login_required("advogado")
def google_callback():
    code = request.args.get("code")

    if not code:
        return "Erro ao autenticar com Google", 400

    usuario_id = session["usuario_id"]
    save_token(code, usuario_id)

    flash("Google Agenda conectada com sucesso.", "success")
    return redirect(url_for("adv.painel_advogado"))


@auth_bp.route("/conectar-google")
@login_required("advogado")
def conectar_google():
    usuario_id = session["usuario_id"]
    auth_url, state = get_auth_url(usuario_id)
    session["google_oauth_state"] = state
    return redirect(auth_url)