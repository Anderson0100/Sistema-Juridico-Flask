import os

from flask import abort, redirect, url_for
from werkzeug.security import generate_password_hash

from app import app
from models import Usuario, Processo, ProcessoHistorico, Prazo
from services.db import db
from utils.phone import normalizar_telefone_brasil

from datetime import datetime as dt, timedelta


@app.route("/seed")
def seed():
    if os.getenv("ALLOW_SEED", "").lower() != "true":
        abort(404)

    db.drop_all()
    db.create_all()

    admin = Usuario(
        nome="Administrador",
        email="admin@teste.com",
        senha=generate_password_hash("123456"),
        tipo="admin"
    )

    adv1 = Usuario(nome="Dr João", email="joao@adv.com", senha=generate_password_hash("123456"), tipo="advogado")
    adv2 = Usuario(nome="Dra Maria", email="maria@adv.com", senha=generate_password_hash("123456"), tipo="advogado")
    adv3 = Usuario(nome="Dr Pedro", email="pedro@adv.com", senha=generate_password_hash("123456"), tipo="advogado")

    db.session.add_all([admin, adv1, adv2, adv3])
    db.session.commit()

    advogados = [adv1, adv2, adv3]
    clientes = []

    for i in range(1, 11):
        if i <= 4:
            advogado = adv1
        elif i <= 7:
            advogado = adv2
        else:
            advogado = adv3

        cliente = Usuario(
            nome=f"Cliente {i}",
            cpf=f"10000000{i}",
            data_nascimento="1990-01-01",
            telefone=normalizar_telefone_brasil(f"87952800{i:02d}"),
            tipo="cliente",
            advogado_id=advogado.id
        )
        clientes.append(cliente)

    db.session.add_all(clientes)
    db.session.commit()

    processos = []

    for i, cliente in enumerate(clientes):
        advogado = advogados[i % 3]

        processo = Processo(
            numero=f"2025.000{i+1}",
            status="Em andamento" if i < 7 else "Concluído",
            prioridade="Urgente" if i in [1, 4, 7] else "Normal",
            cliente_id=cliente.id,
            advogado_id=advogado.id,
            criado_por=advogado.id,
            descricao="Processo de teste"
        )

        if i < 4:
            processo.data_audiencia = (dt.now() + timedelta(days=i + 1)).strftime("%Y-%m-%d")
            processo.hora_audiencia = "10:00"

        db.session.add(processo)
        db.session.commit()
        processos.append(processo)

        db.session.add(ProcessoHistorico(
            processo_id=processo.id,
            usuario_id=advogado.id,
            acao="Processo criado"
        ))

    for i, p in enumerate(processos):
        if i % 2 == 0:
            prazo = Prazo(
                titulo=f"Prazo do processo {p.numero}",
                descricao="Prazo legal",
                data_vencimento=(dt.now() + timedelta(days=i + 2)).date(),
                processo_id=p.id
            )
            db.session.add(prazo)

    db.session.commit()

    return "🔥 Sistema populado com sucesso! Agora teste como Admin, Advogado e Cliente."
