import os
import re
from datetime import date as dt_date

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from core.auth import login_required
from models import (
    Usuario,
    Processo,
    SistemaLog,
    ProcessoArquivo,
    ProcessoTag,
    ProcessoHistorico,
    Observacao,
    Prazo,
    MovimentacaoProcessual,
    NotificacaoCliente,
    AtendimentoInterno,
    AgendamentoAtendimento,
    RecadoInterno,
)
from services.db import db
from utils.phone import limpar_numero, normalizar_telefone_brasil
from utils.logs import log_sistema
from whatsapp.state import FILA_ATENDIMENTO
from whatsapp.helpers import liberar_atendimento_humano


admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin")
@login_required("admin")
def painel_admin():
    advogados = Usuario.query.filter_by(tipo="advogado").all()

    mapa_processos = {}
    for a in advogados:
        mapa_processos[a.id] = Processo.query.filter_by(advogado_id=a.id).count()

    clientes = Usuario.query.filter_by(tipo="cliente").all()
    processos = Processo.query.all()

    total_advogados = len(advogados)
    total_clientes = len(clientes)
    total_processos = len(processos)
    em_andamento = Processo.query.filter_by(status="Em andamento").count()
    concluidos = Processo.query.filter_by(status="Concluído").count()

    historico = SistemaLog.query.order_by(SistemaLog.data.desc()).limit(200).all()

    fila_atendimento = FILA_ATENDIMENTO[:]

    data_filtro = request.args.get("data", "").strip()
    if not data_filtro:
        data_filtro = dt_date.today().strftime("%Y-%m-%d")

    agenda_do_dia = AgendamentoAtendimento.query.filter(
        AgendamentoAtendimento.data_agendada == data_filtro
    ).order_by(
        AgendamentoAtendimento.hora_agendada.asc(),
        AgendamentoAtendimento.criado_em.asc()
    ).all()

    proximos_agendamentos = AgendamentoAtendimento.query.filter(
        AgendamentoAtendimento.data_agendada >= data_filtro
    ).order_by(
        AgendamentoAtendimento.data_agendada.asc(),
        AgendamentoAtendimento.hora_agendada.asc()
    ).limit(15).all()

    recados_recentes = RecadoInterno.query.order_by(
        RecadoInterno.criado_em.desc()
    ).limit(20).all()

    total_agenda_dia = len(agenda_do_dia)

    return render_template(
        "admin.html",
        advogados=advogados,
        clientes=clientes,
        processos=processos,
        historico=historico,
        total_advogados=total_advogados,
        total_clientes=total_clientes,
        total_processos=total_processos,
        em_andamento=em_andamento,
        concluidos=concluidos,
        mapa_processos=mapa_processos,
        fila_atendimento=fila_atendimento,
        agenda_do_dia=agenda_do_dia,
        proximos_agendamentos=proximos_agendamentos,
        recados_recentes=recados_recentes,
        data_filtro=data_filtro,
        total_agenda_dia=total_agenda_dia,
    )


@admin_bp.route("/admin/fila/proximo", methods=["POST"])
@login_required("admin")
def admin_passar_proximo_fila():
    numero = request.form.get("numero", "")
    numero = limpar_numero(numero)

    if not numero:
        flash("Número não informado.", "danger")
        return redirect(url_for("admin.painel_admin"))

    ok = liberar_atendimento_humano(numero)

    if ok:
        log_sistema(f"Admin passou o próximo da fila: {numero}")
        flash(f"Fila avançada para {numero}.", "success")
    else:
        flash("Erro ao avançar a fila.", "danger")

    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/agendamentos/novo", methods=["POST"])
@login_required("admin")
def admin_novo_agendamento():
    nome_cliente = request.form.get("nome_cliente", "").strip()
    telefone = request.form.get("telefone", "").strip()
    assunto = request.form.get("assunto", "").strip()
    observacao = request.form.get("observacao", "").strip()
    data_agendada = request.form.get("data_agendada", "").strip()
    hora_agendada = request.form.get("hora_agendada", "").strip()
    advogado_id = request.form.get("advogado_id", type=int)

    if not nome_cliente or not advogado_id or not data_agendada or not hora_agendada:
        flash("Nome, advogado, data e hora são obrigatórios.", "danger")
        return redirect(url_for("admin.painel_admin"))

    telefone_normalizado = normalizar_telefone_brasil(telefone)

    if telefone and not telefone_normalizado:
        flash("Telefone inválido. Use DDD + número sem o 9. Ex: 87952804", "danger")
        return redirect(url_for("admin.painel_admin"))

    cliente = None
    if telefone_normalizado:
        cliente = Usuario.query.filter_by(
            tipo="cliente",
            telefone=telefone_normalizado
        ).first()

    agendamento = AgendamentoAtendimento(
        cliente_id=cliente.id if cliente else None,
        advogado_id=advogado_id,
        criado_por=session.get("usuario_id"),
        nome_cliente=nome_cliente,
        telefone=telefone_normalizado if telefone_normalizado else None,
        assunto=assunto,
        observacao=observacao,
        data_agendada=data_agendada,
        hora_agendada=hora_agendada,
        status="Marcado"
    )

    db.session.add(agendamento)
    db.session.commit()

    log_sistema(f"Admin criou agendamento presencial para {nome_cliente}")
    flash("Agendamento criado com sucesso.", "success")
    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/agendamentos/<int:id>/status", methods=["POST"])
@login_required("admin")
def admin_atualizar_status_agendamento(id):
    agendamento = AgendamentoAtendimento.query.get_or_404(id)

    novo_status = request.form.get("status", "").strip()
    status_validos = ["Marcado", "Confirmado", "Concluído", "Cancelado"]

    if novo_status not in status_validos:
        flash("Status inválido.", "danger")
        return redirect(url_for("admin.painel_admin"))

    agendamento.status = novo_status
    db.session.commit()

    log_sistema(f"Admin atualizou status do agendamento {id} para {novo_status}")
    flash("Status do agendamento atualizado.", "success")
    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/agendamentos/<int:id>/excluir", methods=["POST"])
@login_required("admin")
def admin_excluir_agendamento(id):
    agendamento = AgendamentoAtendimento.query.get_or_404(id)

    nome_cliente = agendamento.nome_cliente
    db.session.delete(agendamento)
    db.session.commit()

    log_sistema(f"Admin excluiu agendamento de {nome_cliente}")
    flash("Agendamento excluído com sucesso.", "success")
    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/atendimentos/novo", methods=["POST"])
@login_required("admin")
def admin_novo_atendimento():
    nome_cliente = request.form.get("nome_cliente", "").strip()
    telefone = request.form.get("telefone", "").strip()
    assunto = request.form.get("assunto", "").strip()
    observacao = request.form.get("observacao", "").strip()
    data_agendada = request.form.get("data_agendada", "").strip()
    hora_agendada = request.form.get("hora_agendada", "").strip()
    advogado_id = request.form.get("advogado_id", type=int)
    tipo = request.form.get("tipo", "atendimento").strip()

    if not nome_cliente or not assunto or not data_agendada:
        flash("Nome do cliente, assunto e data são obrigatórios.", "danger")
        return redirect(url_for("admin.painel_admin"))

    telefone_normalizado = normalizar_telefone_brasil(telefone)

    if telefone and not telefone_normalizado:
        flash("Telefone inválido. Use DDD + número sem o 9. Ex: 87952804", "danger")
        return redirect(url_for("admin.painel_admin"))

    cliente = None
    if telefone_normalizado:
        cliente = Usuario.query.filter_by(
            tipo="cliente",
            telefone=telefone_normalizado
        ).first()

    atendimento = AtendimentoInterno(
        cliente_id=cliente.id if cliente else None,
        advogado_id=advogado_id if advogado_id else None,
        criado_por=session.get("usuario_id"),
        nome_cliente=nome_cliente,
        telefone=telefone_normalizado if telefone_normalizado else None,
        assunto=assunto,
        observacao=observacao,
        tipo=tipo,
        data_agendada=data_agendada or None,
        hora_agendada=hora_agendada or None,
        status="Pendente"
    )

    db.session.add(atendimento)
    db.session.commit()

    log_sistema(
        f"Admin criou compromisso interno para {nome_cliente} - tipo: {tipo} - assunto: {assunto}"
    )
    flash("Compromisso/atendimento registrado com sucesso.", "success")
    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/recados/novo", methods=["POST"])
@login_required("admin")
def admin_novo_recado():
    nome_cliente = request.form.get("nome_cliente", "").strip()
    telefone = request.form.get("telefone", "").strip()
    assunto = request.form.get("assunto", "").strip()
    recado = request.form.get("recado", "").strip()
    canal = request.form.get("canal", "ligacao").strip()
    advogado_id = request.form.get("advogado_id", type=int)

    if not nome_cliente or not assunto or not recado:
        flash("Nome, assunto e recado são obrigatórios.", "danger")
        return redirect(url_for("admin.painel_admin"))

    telefone_normalizado = normalizar_telefone_brasil(telefone)

    if telefone and not telefone_normalizado:
        flash("Telefone inválido. Use DDD + número sem o 9. Ex: 87952804", "danger")
        return redirect(url_for("admin.painel_admin"))

    cliente = None
    if telefone_normalizado:
        cliente = Usuario.query.filter_by(
            tipo="cliente",
            telefone=telefone_normalizado
        ).first()

    novo_recado = RecadoInterno(
        cliente_id=cliente.id if cliente else None,
        advogado_id=advogado_id if advogado_id else None,
        criado_por=session.get("usuario_id"),
        nome_cliente=nome_cliente,
        telefone=telefone_normalizado if telefone_normalizado else None,
        canal=canal,
        assunto=assunto,
        recado=recado,
        status="Pendente"
    )

    db.session.add(novo_recado)
    db.session.commit()

    log_sistema(f"Admin criou recado interno para {nome_cliente} - {assunto}")
    flash("Recado salvo com sucesso.", "success")
    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/recados/<int:id>/status", methods=["POST"])
@login_required("admin")
def admin_atualizar_status_recado(id):
    recado = RecadoInterno.query.get_or_404(id)

    novo_status = request.form.get("status", "").strip()
    status_validos = ["Pendente", "Lido", "Resolvido"]

    if novo_status not in status_validos:
        flash("Status inválido.", "danger")
        return redirect(url_for("admin.painel_admin"))

    recado.status = novo_status
    db.session.commit()

    log_sistema(f"Admin atualizou status do recado {id} para {novo_status}")
    flash("Status do recado atualizado.", "success")
    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/recados/<int:id>/excluir", methods=["POST"])
@login_required("admin")
def admin_excluir_recado(id):
    recado = RecadoInterno.query.get_or_404(id)

    nome_cliente = recado.nome_cliente
    db.session.delete(recado)
    db.session.commit()

    log_sistema(f"Admin excluiu recado de {nome_cliente}")
    flash("Recado excluído com sucesso.", "success")
    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/advogado/novo", methods=["POST"])
@login_required("admin")
def admin_novo_advogado():
    from werkzeug.security import generate_password_hash

    nome = request.form["nome"]
    email = request.form["email"].strip().lower()
    senha = generate_password_hash(request.form["senha"])

    if Usuario.query.filter_by(email=email).first():
        flash("Já existe um advogado com esse email.", "danger")
        return redirect(url_for("admin.painel_admin"))

    adv = Usuario(
        nome=nome,
        email=email,
        senha=senha,
        tipo="advogado",
        ativo=True
    )

    db.session.add(adv)
    db.session.commit()

    log_sistema(f"Admin criou advogado {nome}")
    flash("Advogado criado com sucesso.", "success")
    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/advogado/<int:id>/toggle")
@login_required("admin")
def admin_toggle_advogado(id):
    adv = Usuario.query.get_or_404(id)
    adv.ativo = not adv.ativo

    db.session.commit()

    status = "ativado" if adv.ativo else "bloqueado"
    log_sistema(f"Admin {status} advogado {adv.nome}")

    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/cliente/<int:id>/editar", methods=["GET", "POST"])
@login_required("admin")
def admin_editar_cliente(id):
    cliente = Usuario.query.get_or_404(id)

    if request.method == "POST":
        novo_cpf = re.sub(r"\D", "", request.form["cpf"])

        existe = Usuario.query.filter(
            Usuario.cpf == novo_cpf,
            Usuario.id != cliente.id
        ).first()

        if existe:
            flash("Esse CPF já está em uso", "danger")
            return redirect(url_for("admin.admin_editar_cliente", id=id))

        cliente.nome = request.form["nome"]
        cliente.cpf = novo_cpf
        cliente.data_nascimento = request.form["data_nascimento"]
        cliente.telefone = normalizar_telefone_brasil(request.form.get("telefone", ""))

        db.session.commit()
        flash("Cliente atualizado", "success")
        return redirect(url_for("admin.painel_admin"))

    return render_template("cliente_editar.html", cliente=cliente)


@admin_bp.route("/admin/cliente/<int:id>/excluir", methods=["POST"])
@login_required("admin")
def admin_excluir_cliente(id):
    cliente = Usuario.query.get_or_404(id)

    processos = Processo.query.filter_by(cliente_id=id).all()

    for processo in processos:
        arquivos = ProcessoArquivo.query.filter_by(processo_id=processo.id).all()
        for arq in arquivos:
            caminho = os.path.join("uploads", arq.nome_arquivo)
            if os.path.exists(caminho):
                os.remove(caminho)

        ProcessoArquivo.query.filter_by(processo_id=processo.id).delete()
        ProcessoTag.query.filter_by(processo_id=processo.id).delete()
        ProcessoHistorico.query.filter_by(processo_id=processo.id).delete()
        Observacao.query.filter_by(processo_id=processo.id).delete()
        Prazo.query.filter_by(processo_id=processo.id).delete()
        MovimentacaoProcessual.query.filter_by(processo_id=processo.id).delete()

        db.session.delete(processo)

    NotificacaoCliente.query.filter_by(cliente_id=id).delete()

    db.session.delete(cliente)
    db.session.commit()

    log_sistema(f"Admin excluiu cliente {cliente.nome}")
    flash("Cliente excluído com sucesso", "success")
    return redirect(url_for("admin.painel_admin"))


@admin_bp.route("/admin/processo/<int:id>/excluir", methods=["POST"])
@login_required("admin")
def admin_excluir_processo(id):
    processo = Processo.query.get_or_404(id)

    arquivos = ProcessoArquivo.query.filter_by(processo_id=id).all()
    for arq in arquivos:
        caminho = os.path.join("uploads", arq.nome_arquivo)
        if os.path.exists(caminho):
            os.remove(caminho)

    ProcessoArquivo.query.filter_by(processo_id=id).delete()
    ProcessoTag.query.filter_by(processo_id=id).delete()
    ProcessoHistorico.query.filter_by(processo_id=id).delete()
    Observacao.query.filter_by(processo_id=id).delete()
    Prazo.query.filter_by(processo_id=id).delete()
    MovimentacaoProcessual.query.filter_by(processo_id=id).delete()

    db.session.delete(processo)
    db.session.commit()

    log_sistema(f"Admin excluiu processo {processo.numero}")
    flash("Processo excluído com sucesso", "success")
    return redirect(url_for("admin.painel_admin"))