import os
import uuid

from datetime import datetime as dt, date as dt_date, timedelta
from flask import render_template, request, redirect, url_for, session, flash, send_from_directory, abort
from werkzeug.utils import secure_filename

from app import app
from core.auth import login_required, pode_editar_processo, pode_ver_processo
from models import *
from services.db import db
from services.monitor import verificar_nova_movimentacao
from services.whatsapp_service import enviar_mensagem
from google_calendar import get_calendar_service, criar_evento_google
from utils.files import allowed_file
from utils.logs import log_sistema


@app.route("/monitorar/<int:id>")
@login_required()
def monitorar_processo(id):
    processo = Processo.query.get_or_404(id)

    if not pode_editar_processo(processo):
        abort(403)

    houve_atualizacao = verificar_nova_movimentacao(processo)

    if houve_atualizacao:
        db.session.commit()
        flash("Nova movimentação detectada!", "success")
    else:
        flash("Sem nova movimentação.", "info")

    return redirect(url_for("detalhe_processo", id=id))


@app.route("/debug-monitor/<int:id>")
@login_required("admin")
def debug_monitor(id):
    processo = Processo.query.get_or_404(id)
    from services.consulta import consultar_processo
    dados = consultar_processo(processo.numero)
    return str(dados)


@app.route("/processo/<int:id>/prazo", methods=["POST"], endpoint="adicionar_prazo")
@login_required()
def adicionar_prazo(id):
    processo = Processo.query.get_or_404(id)

    if not pode_editar_processo(processo):
        flash("Você não tem permissão para adicionar prazo neste processo", "danger")
        return redirect(url_for("detalhe_processo", id=id))

    titulo = request.form["titulo"]
    data_vencimento = dt.strptime(request.form["data"], "%Y-%m-%d").date()

    prazo = Prazo(
        titulo=titulo,
        descricao=titulo,
        data_vencimento=data_vencimento,
        status="Aberto",
        processo_id=id
    )

    db.session.add(prazo)

    db.session.add(ProcessoHistorico(
        processo_id=id,
        acao=f"Prazo criado: {titulo} ({data_vencimento.strftime('%d/%m/%Y')})"
    ))

    db.session.commit()

    return redirect(url_for("detalhe_processo", id=id))


@app.route("/prazo/<int:id>/excluir", methods=["POST"])
@login_required()
def excluir_prazo(id):
    prazo = Prazo.query.get_or_404(id)
    processo = Processo.query.get_or_404(prazo.processo_id)

    if not pode_editar_processo(processo):
        abort(403)

    processo_id = prazo.processo_id

    db.session.add(ProcessoHistorico(
        processo_id=processo_id,
        acao=f"Prazo excluído: {prazo.titulo}"
    ))

    db.session.delete(prazo)
    db.session.commit()

    return redirect(url_for("detalhe_processo", id=processo_id))


@app.route('/processos/<int:id>/observacao', methods=['POST'])
@login_required()
def adicionar_observacao(id):
    processo = Processo.query.get_or_404(id)

    if not pode_editar_processo(processo):
        abort(403)

    texto = request.form['texto']

    nova = Observacao(
        texto=texto,
        processo_id=processo.id,
        advogado_id=session['usuario_id']
    )

    db.session.add(nova)

    db.session.add(ProcessoHistorico(
        processo_id=id,
        usuario_id=session["usuario_id"],
        acao="Observação adicionada"
    ))

    db.session.commit()

    flash("Observação adicionada com sucesso", "success")
    return redirect(url_for('detalhe_processo', id=id))

@app.route("/observacao/<int:id>/excluir", methods=["POST"])
@login_required()
def excluir_observacao(id):
    obs = Observacao.query.get_or_404(id)
    processo_id = obs.processo_id

    if session.get("usuario_tipo") != "admin" and obs.advogado_id != session.get("usuario_id"):
        abort(403)

    db.session.add(ProcessoHistorico(
        processo_id=processo_id,
        usuario_id=session.get("usuario_id"),
        acao="Observação excluída"
    ))

    db.session.delete(obs)
    db.session.commit()

    flash("Observação excluída com sucesso.", "success")
    return redirect(url_for("detalhe_processo", id=processo_id))

@app.route('/advogado/processos')
@login_required('advogado')
def processos_advogado():
    advogado_id = session['usuario_id']
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')
    prioridade = request.args.get('prioridade')
    cliente = request.args.get('cliente')
    busca = request.args.get('busca')

    query = Processo.query.filter_by(advogado_id=advogado_id)

    if status:
        query = query.filter(Processo.status == status)

    if prioridade:
        query = query.filter(Processo.prioridade == prioridade)

    if cliente:
        query = query.filter(Processo.cliente_id == int(cliente))

    if busca:
        query = query.filter(Processo.numero.ilike(f'%{busca}%'))

    processos = query.order_by(Processo.id.desc()).paginate(
        page=page,
        per_page=10,
        error_out=False
    )

    clientes = Usuario.query.filter_by(
        tipo='cliente',
        advogado_id=advogado_id
    ).all()

    return render_template(
        'processos.html',
        processos=processos,
        clientes=clientes,
        filtros={
            'status': status,
            'prioridade': prioridade,
            'cliente': cliente,
            'busca': busca
        },
        advogado_logado_id=session["usuario_id"],
        tipo_usuario=session["usuario_tipo"]
    )


@app.route('/advogado/processos/novo', methods=['GET', 'POST'])
@login_required('advogado')
def novo_processo():
    if request.method == 'POST':

        processo = Processo(
            numero=request.form['numero'],
            status=request.form['status'],
            prioridade=request.form['prioridade'],
            descricao=request.form['observacoes'],
            cliente_id=int(request.form['cliente_id']),
            advogado_id=session['usuario_id'],
            criado_por=session['usuario_id']
        )

        db.session.add(processo)
        db.session.commit()

        from services.consulta import consultar_processo
        dados = consultar_processo(request.form["numero"])

        if dados:
            processo.ultima_movimentacao = dados["ultima_movimentacao"]
            processo.data_movimentacao = dados["data"]
            processo.tribunal = dados["tribunal"]

        db.session.add(NotificacaoCliente(
            cliente_id=processo.cliente_id,
            mensagem=f"Um novo processo foi criado para você: {processo.numero}"
        ))
        db.session.commit()

        prazo_data = request.form.get('prazo_data')
        prazo_titulo = request.form.get('prazo_titulo')

        if prazo_data and prazo_titulo:
            prazo = Prazo(
                titulo=prazo_titulo,
                descricao=prazo_titulo,
                data_vencimento=dt.strptime(prazo_data, "%Y-%m-%d").date(),
                processo_id=processo.id
            )
            db.session.add(prazo)
            db.session.commit()

        obs = request.form.get("observacoes")

        if obs:
            db.session.add(Observacao(
                texto=obs,
                processo_id=processo.id,
                advogado_id=session["usuario_id"]
            ))
            db.session.commit()

        db.session.add(ProcessoHistorico(
            acao='Processo criado',
            processo_id=processo.id
        ))

        log_sistema(f"Criou processo {processo.numero}")

        data_audiencia = request.form.get('data_audiencia')
        hora_audiencia = request.form.get('hora_audiencia')

        if data_audiencia and hora_audiencia:
            try:
                event_id = criar_evento_google(
                    session["usuario_id"],
                    f"Audiência - Processo {processo.numero}",
                    processo.descricao or "",
                    data_audiencia,
                    hora_audiencia
                )
            except Exception:
                event_id = None

            processo.data_audiencia = data_audiencia
            processo.hora_audiencia = hora_audiencia
            processo.google_event_id = event_id

        tags = request.form.get('tags')
        if tags:
            for tag in tags.split(','):
                db.session.add(ProcessoTag(
                    nome=tag.strip(),
                    processo_id=processo.id
                ))

        for arquivo in request.files.getlist('arquivos'):
            if arquivo and allowed_file(arquivo):
                nome_salvo = f"{uuid.uuid4()}_{secure_filename(arquivo.filename)}"
                arquivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nome_salvo))

                db.session.add(ProcessoArquivo(
                    nome_original=arquivo.filename,
                    nome_arquivo=nome_salvo,
                    processo_id=processo.id
                ))

                db.session.add(ProcessoHistorico(
                    acao=f'Arquivo adicionado: {arquivo.filename}',
                    processo_id=processo.id
                ))

                log_sistema(f"Adicionou PDF {arquivo.filename} no processo {processo.numero}")

        db.session.commit()
        return redirect(url_for('processos_advogado'))

    clientes = Usuario.query.filter_by(
        tipo='cliente',
        advogado_id=session['usuario_id']
    ).all()

    return render_template('processo_novo.html', clientes=clientes)


@app.route("/processo/<int:id>", methods=["GET", "POST"], endpoint="detalhe_processo")
@login_required()
def detalhe_processo(id):
    processo = Processo.query.get_or_404(id)

    if not pode_ver_processo(processo):
        abort(403)

    pode_editar = pode_editar_processo(processo)

    if request.method == "POST":
        if not pode_editar:
            flash("Você não tem permissão para alterar este processo.", "danger")
            return redirect(url_for("detalhe_processo", id=id))

        processo.status = request.form.get("status")
        processo.prioridade = request.form.get("prioridade")
        processo.descricao = request.form.get("observacoes")

        db.session.add(ProcessoHistorico(
            processo_id=id,
            usuario_id=session["usuario_id"],
            acao=f"Processo atualizado (Status: {processo.status})"
        ))

        log_sistema(f"Atualizou processo {processo.numero}")

        db.session.add(NotificacaoCliente(
            cliente_id=processo.cliente_id,
            mensagem=f"O status do seu processo {processo.numero} foi alterado para {processo.status}"
        ))

        try:
            telefone = processo.cliente.telefone
            if telefone:
                enviar_mensagem(
                    telefone,
                    f"Seu processo {processo.numero} foi atualizado para {processo.status}"
                )
        except Exception as e:
            print("Erro ao enviar WhatsApp:", e)

        data_aud = request.form.get("data_audiencia")
        hora_aud = request.form.get("hora_audiencia")

        if data_aud and hora_aud:
            db.session.add(NotificacaoCliente(
                cliente_id=processo.cliente_id,
                mensagem=f"Audiência marcada para {data_aud} às {hora_aud} no processo {processo.numero}"
            ))

            if processo.google_event_id:
                service = get_calendar_service(session["usuario_id"])
                if service:
                    try:
                        service.events().delete(
                            calendarId="primary",
                            eventId=processo.google_event_id
                        ).execute()
                    except Exception:
                        pass

            event_id = criar_evento_google(
                session["usuario_id"],
                f"Audiência - Processo {processo.numero}",
                processo.descricao or "",
                data_aud,
                hora_aud
            )

            processo.data_audiencia = data_aud
            processo.hora_audiencia = hora_aud
            processo.google_event_id = event_id

            db.session.add(ProcessoHistorico(
                processo_id=id,
                acao=f"Audiência definida para {data_aud} às {hora_aud}"
            ))

        if "arquivos" in request.files:
            for arquivo in request.files.getlist("arquivos"):
                if arquivo and allowed_file(arquivo):
                    nome_salvo = f"{uuid.uuid4()}_{secure_filename(arquivo.filename)}"
                    arquivo.save(os.path.join(app.config["UPLOAD_FOLDER"], nome_salvo))

                    db.session.add(ProcessoArquivo(
                        nome_original=arquivo.filename,
                        nome_arquivo=nome_salvo,
                        processo_id=id
                    ))

                    db.session.add(ProcessoHistorico(
                        processo_id=id,
                        acao=f"Arquivo adicionado: {arquivo.filename}"
                    ))

        db.session.commit()
        return redirect(url_for("detalhe_processo", id=id))

    tags = ProcessoTag.query.filter_by(processo_id=id).all()
    arquivos = ProcessoArquivo.query.filter_by(processo_id=id).all()
    historico = ProcessoHistorico.query.filter_by(
        processo_id=id
    ).order_by(ProcessoHistorico.data.desc()).all()
    prazos = Prazo.query.filter_by(
        processo_id=id
    ).order_by(Prazo.data_vencimento.asc()).all()

    hoje = dt_date.today()
    amanha = hoje + timedelta(days=1)

    alertas = []
    for p in prazos:
        if p.data_vencimento == amanha:
            alertas.append(f"O prazo '{p.titulo}' vence amanhã!")
        elif p.data_vencimento < hoje:
            alertas.append(f"O prazo '{p.titulo}' está vencido!")

    movimentacoes = MovimentacaoProcessual.query.filter_by(
        processo_id=id
    ).order_by(MovimentacaoProcessual.id.desc()).all()

    return render_template(
        "processo_detalhe.html",
        processo=processo,
        tags=tags,
        arquivos=arquivos,
        historico=historico,
        prazos=prazos,
        hoje=hoje,
        alertas=alertas,
        movimentacoes=movimentacoes,
        pode_editar=pode_editar
    )


@app.route('/advogado/processos/<int:id>/excluir', methods=['POST'])
@login_required('advogado')
def excluir_processo(id):
    processo = Processo.query.get_or_404(id)

    if processo.advogado_id != session["usuario_id"]:
        flash("Você não tem permissão para excluir este processo", "danger")
        return redirect(url_for("processos_advogado"))

    if processo.google_event_id:
        service = get_calendar_service(session["usuario_id"])
        if service:
            try:
                service.events().delete(
                    calendarId='primary',
                    eventId=processo.google_event_id
                ).execute()
            except Exception:
                pass

    arquivos = ProcessoArquivo.query.filter_by(processo_id=id).all()
    for arq in arquivos:
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], arq.nome_arquivo)
        if os.path.exists(caminho):
            os.remove(caminho)

    ProcessoArquivo.query.filter_by(processo_id=id).delete()
    ProcessoTag.query.filter_by(processo_id=id).delete()
    ProcessoHistorico.query.filter_by(processo_id=id).delete()

    log_sistema(f"Excluiu o processo {processo.numero}")

    db.session.delete(processo)
    db.session.commit()

    flash("Processo excluído", "success")
    return redirect(url_for("processos_advogado"))


@app.route("/arquivo/<int:id>/download")
@login_required()
def baixar_pdf(id):
    arquivo = ProcessoArquivo.query.get_or_404(id)
    processo = Processo.query.get_or_404(arquivo.processo_id)

    if not pode_ver_processo(processo):
        abort(403)

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        arquivo.nome_arquivo,
        as_attachment=True
    )


@app.route("/processo/arquivo/<int:id>/excluir", methods=["POST"])
@login_required()
def excluir_arquivo(id):
    arquivo = ProcessoArquivo.query.get_or_404(id)
    processo = Processo.query.get_or_404(arquivo.processo_id)

    if not pode_editar_processo(processo):
        abort(403)

    caminho = os.path.join(app.config["UPLOAD_FOLDER"], arquivo.nome_arquivo)
    if os.path.exists(caminho):
        os.remove(caminho)

    db.session.add(ProcessoHistorico(
        processo_id=arquivo.processo_id,
        acao=f"Arquivo removido: {arquivo.nome_original}"
    ))

    log_sistema(f"Removeu arquivo {arquivo.nome_original}")

    db.session.delete(arquivo)
    db.session.commit()

    return redirect(url_for("detalhe_processo", id=processo.id))
