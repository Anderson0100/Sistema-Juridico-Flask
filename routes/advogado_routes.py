import re

from datetime import datetime as dt, date as dt_date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash

from core.auth import login_required
from google_calendar import get_calendar_service
from models import (
    Usuario,
    Processo,
    Prazo,
    Mensagem,
    ProcessoArquivo,
    AgendamentoAtendimento,
    RecadoInterno,
    AtendimentoInterno,
)
from services.db import db
from utils.phone import normalizar_telefone_brasil
from utils.logs import log_sistema


adv_bp = Blueprint("adv", __name__)


@adv_bp.route("/advogado/audiencias")
@login_required("advogado")
def lista_audiencias():
    advogado_id = session["usuario_id"]

    audiencias = Processo.query.filter(
        Processo.advogado_id == advogado_id,
        Processo.data_audiencia != None
    ).order_by(
        Processo.data_audiencia.asc()
    ).all()

    return render_template("audiencias.html", audiencias=audiencias)


@adv_bp.route("/advogado/clientes")
@login_required("advogado")
def clientes_advogado():
    advogado_id = session["usuario_id"]

    clientes = Usuario.query.filter_by(
        tipo="cliente",
        advogado_id=advogado_id
    ).all()

    return render_template("clientes.html", clientes=clientes)


@adv_bp.route("/advogado/clientes/novo", methods=["GET", "POST"])
@login_required("advogado")
def novo_cliente():
    if request.method == "POST":
        cpf = re.sub(r"\D", "", request.form["cpf"])

        if Usuario.query.filter_by(cpf=cpf).first():
            flash("Já existe um cliente com esse CPF", "danger")
            return redirect(url_for("adv.novo_cliente"))

        senha_temp = "123456"

        cliente = Usuario(
            nome=request.form["nome"],
            cpf=cpf,
            data_nascimento=request.form["data_nascimento"],
            email=request.form.get("email"),
            telefone=normalizar_telefone_brasil(request.form.get("telefone")),
            senha=generate_password_hash(senha_temp),
            tipo="cliente",
            advogado_id=session["usuario_id"]
        )

        db.session.add(cliente)
        db.session.commit()

        flash(f"Cliente criado! Senha inicial: {senha_temp}", "success")
        return redirect(url_for("adv.clientes_advogado"))

    return render_template("cliente_novo.html")


@adv_bp.route("/advogado/clientes/<int:id>/editar", methods=["GET", "POST"])
@login_required("advogado")
def editar_cliente(id):
    cliente = Usuario.query.get_or_404(id)

    if session.get("usuario_tipo") != "admin" and cliente.advogado_id != session["usuario_id"]:
        abort(403)

    if request.method == "POST":
        cliente.nome = request.form["nome"]
        cliente.data_nascimento = request.form["data_nascimento"]
        cliente.telefone = normalizar_telefone_brasil(request.form.get("telefone", ""))
        db.session.commit()

        flash("Cliente atualizado com sucesso", "success")
        return redirect(url_for("adv.clientes_advogado"))

    return render_template("cliente_editar.html", cliente=cliente)


@adv_bp.route("/painel/advogado")
@login_required("advogado")
def painel_advogado():
    advogado_id = session["usuario_id"]
    hoje = dt_date.today()
    hoje_str = hoje.strftime("%Y-%m-%d")
    amanha = hoje + timedelta(days=1)
    limite_alerta_audiencia = hoje + timedelta(days=3)
    limite_audiencia_7_dias = hoje + timedelta(days=7)
    q = request.args.get("q", "").strip()

    service = get_calendar_service(advogado_id)
    google_conectado = bool(service)

    processos_do_advogado = Processo.query.filter_by(advogado_id=advogado_id)

    audiencias = processos_do_advogado.filter(
        Processo.data_audiencia.isnot(None)
    ).order_by(Processo.data_audiencia.asc()).limit(5).all()

    prazos = Prazo.query.join(Processo).filter(
        Processo.advogado_id == advogado_id
    ).order_by(Prazo.data_vencimento.asc()).all()

    alertas = []

    for p in prazos:
        if p.data_vencimento < hoje:
            alertas.append({
                "tipo": "vencido",
                "texto": f"Prazo vencido: {p.titulo} (Proc {p.processo.numero})"
            })
        elif p.data_vencimento == hoje:
            alertas.append({
                "tipo": "hoje",
                "texto": f"Prazo vence hoje: {p.titulo} (Proc {p.processo.numero})"
            })
        elif p.data_vencimento == amanha:
            alertas.append({
                "tipo": "amanha",
                "texto": f"Prazo vence amanhã: {p.titulo} (Proc {p.processo.numero})"
            })

    for proc in audiencias:
        try:
            if isinstance(proc.data_audiencia, str):
                data_aud = dt.strptime(proc.data_audiencia, "%Y-%m-%d").date()
            else:
                data_aud = proc.data_audiencia

            if hoje <= data_aud <= limite_alerta_audiencia:
                alertas.append({
                    "tipo": "audiencia",
                    "texto": f"Audiência em {data_aud.strftime('%d/%m')} — Processo {proc.numero}"
                })
        except Exception:
            pass

    notificacoes = []

    urgentes_lista = processos_do_advogado.filter_by(prioridade="Urgente").all()

    for p in urgentes_lista:
        notificacoes.append(f"🔥 Processo {p.numero} está marcado como URGENTE")

    sete_dias_atras = dt.now() - timedelta(days=7)
    parados = processos_do_advogado.filter(
        Processo.data_criacao < sete_dias_atras
    ).all()

    for p in parados:
        notificacoes.append(f"⏳ Processo {p.numero} está sem revisão há mais de 7 dias")

    resultados = None

    if q:
        resultados = {
            "processos": Processo.query.filter(
                Processo.advogado_id == advogado_id,
                Processo.numero.ilike(f"%{q}%")
            ).all(),

            "clientes": Usuario.query.filter(
                Usuario.tipo == "cliente",
                Usuario.advogado_id == advogado_id,
                Usuario.nome.ilike(f"%{q}%")
            ).all(),

            "arquivos": ProcessoArquivo.query.join(Processo).filter(
                Processo.advogado_id == advogado_id,
                ProcessoArquivo.nome_original.ilike(f"%{q}%")
            ).all(),

            "prazos": Prazo.query.join(Processo).filter(
                Processo.advogado_id == advogado_id,
                Prazo.titulo.ilike(f"%{q}%")
            ).all()
        }

    prazos_vencidos = Prazo.query.join(Processo).filter(
        Processo.advogado_id == advogado_id,
        Prazo.data_vencimento < hoje
    ).count()

    audiencias_7_dias = 0

    for proc in Processo.query.filter(
        Processo.advogado_id == advogado_id,
        Processo.data_audiencia.isnot(None)
    ).all():
        try:
            if isinstance(proc.data_audiencia, str):
                data_aud = dt.strptime(proc.data_audiencia, "%Y-%m-%d").date()
            else:
                data_aud = proc.data_audiencia

            if hoje <= data_aud <= limite_audiencia_7_dias:
                audiencias_7_dias += 1
        except Exception:
            pass

    ativos = processos_do_advogado.filter_by(status="Em andamento").count()
    concluidos = processos_do_advogado.filter_by(status="Concluído").count()
    total = processos_do_advogado.count()
    taxa = int((concluidos / total) * 100) if total else 0

    mensagens = Mensagem.query.join(
        Processo, Mensagem.processo_id == Processo.id
    ).filter(
        Processo.advogado_id == advogado_id
    ).order_by(
        Mensagem.data.desc()
    ).limit(20).all()

    meus_agendamentos_hoje = AgendamentoAtendimento.query.filter(
        AgendamentoAtendimento.advogado_id == advogado_id,
        AgendamentoAtendimento.data_agendada == hoje_str
    ).order_by(
        AgendamentoAtendimento.hora_agendada.asc()
    ).all()

    proximos_agendamentos = AgendamentoAtendimento.query.filter(
        AgendamentoAtendimento.advogado_id == advogado_id,
        AgendamentoAtendimento.data_agendada >= hoje_str
    ).order_by(
        AgendamentoAtendimento.data_agendada.asc(),
        AgendamentoAtendimento.hora_agendada.asc()
    ).limit(20).all()

    meus_recados = RecadoInterno.query.filter(
        (RecadoInterno.advogado_id == advogado_id) | (RecadoInterno.advogado_id.is_(None))
    ).order_by(
        RecadoInterno.criado_em.desc()
    ).limit(20).all()

    total_agendamentos_hoje = len(meus_agendamentos_hoje)
    total_recados_pendentes = len([r for r in meus_recados if r.status == "Pendente"])

    return render_template(
        "painel_advogado.html",
        total_processos=total,
        em_andamento=ativos,
        concluidos=concluidos,
        urgentes=len(urgentes_lista),
        agenda=audiencias,
        hoje=hoje,
        prazos=prazos,
        alertas=alertas,
        prazos_vencidos=prazos_vencidos,
        audiencias_7_dias=audiencias_7_dias,
        taxa=taxa,
        resultados=resultados,
        q=q,
        notificacoes=notificacoes,
        google_conectado=google_conectado,
        mensagens=mensagens,
        meus_agendamentos_hoje=meus_agendamentos_hoje,
        proximos_agendamentos=proximos_agendamentos,
        meus_recados=meus_recados,
        total_agendamentos_hoje=total_agendamentos_hoje,
        total_recados_pendentes=total_recados_pendentes
    )


@adv_bp.route("/advogado/agendamentos/<int:id>/status", methods=["POST"])
@login_required("advogado")
def advogado_atualizar_status_agendamento(id):
    agendamento = AgendamentoAtendimento.query.get_or_404(id)

    if agendamento.advogado_id != session["usuario_id"]:
        abort(403)

    novo_status = request.form.get("status", "").strip()
    status_validos = ["Marcado", "Confirmado", "Concluído", "Cancelado"]

    if novo_status not in status_validos:
        flash("Status inválido.", "danger")
        return redirect(url_for("adv.painel_advogado"))

    agendamento.status = novo_status
    db.session.commit()

    log_sistema(f"Advogado atualizou agendamento {id} para {novo_status}")
    flash("Status do agendamento atualizado.", "success")
    return redirect(url_for("adv.painel_advogado"))


@adv_bp.route("/advogado/recados/<int:id>/status", methods=["POST"])
@login_required("advogado")
def advogado_atualizar_status_recado(id):
    recado = RecadoInterno.query.get_or_404(id)

    if recado.advogado_id and recado.advogado_id != session["usuario_id"]:
        abort(403)

    novo_status = request.form.get("status", "").strip()
    status_validos = ["Pendente", "Lido", "Resolvido"]

    if novo_status not in status_validos:
        flash("Status inválido.", "danger")
        return redirect(url_for("adv.painel_advogado"))

    recado.status = novo_status
    db.session.commit()

    log_sistema(f"Advogado atualizou recado {id} para {novo_status}")
    flash("Status do recado atualizado.", "success")
    return redirect(url_for("adv.painel_advogado"))


@adv_bp.route("/advogado/atendimentos/<int:id>/status", methods=["POST"])
@login_required("advogado")
def advogado_atualizar_status_atendimento(id):
    atendimento = AtendimentoInterno.query.get_or_404(id)

    if atendimento.advogado_id != session["usuario_id"]:
        abort(403)

    novo_status = request.form.get("status", "").strip()
    status_validos = ["Pendente", "Confirmado", "Concluído", "Cancelado"]

    if novo_status not in status_validos:
        flash("Status inválido.", "danger")
        return redirect(url_for("adv.painel_advogado"))

    atendimento.status = novo_status
    db.session.commit()

    log_sistema(f"Advogado atualizou atendimento {id} para {novo_status}")
    flash("Status do atendimento atualizado.", "success")
    return redirect(url_for("adv.painel_advogado"))