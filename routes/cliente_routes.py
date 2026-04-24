from flask import render_template, session

from app import app
from core.auth import login_required
from models import Processo, NotificacaoCliente


@app.route("/painel/cliente")
@login_required("cliente")
def painel_cliente():
    cliente_id = session["usuario_id"]

    processos = Processo.query.filter_by(cliente_id=cliente_id).all()

    total = len(processos)
    em_andamento = len([p for p in processos if p.status == "Em andamento"])
    concluidos = len([p for p in processos if p.status == "Concluído"])

    proxima = None
    audiencias = [p for p in processos if p.data_audiencia]

    if audiencias:
        audiencias.sort(key=lambda x: x.data_audiencia)
        proxima = audiencias[0]

    notificacoes = NotificacaoCliente.query.filter_by(
        cliente_id=cliente_id,
        lida=False
    ).order_by(NotificacaoCliente.data.desc()).all()

    return render_template(
        "painel_cliente_dashboard.html",
        processos=processos,
        total=total,
        em_andamento=em_andamento,
        concluidos=concluidos,
        proxima=proxima,
        notificacoes=notificacoes
    )