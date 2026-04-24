from datetime import datetime, timedelta

from services.consulta import consultar_processo
from services.db import db
from services.whatsapp_service import enviar_mensagem
from models import Processo, MovimentacaoProcessual, Usuario


def verificar_nova_movimentacao(processo):
    dados = consultar_processo(processo.numero)

    if not dados:
        return False

    nova_data = dados.get("data")
    nova_descricao = (dados.get("ultima_movimentacao") or "").strip()
    novo_tribunal = dados.get("tribunal")

    houve_mudanca = (
        not processo.data_movimentacao
        or processo.data_movimentacao != nova_data
        or (processo.ultima_movimentacao or "").strip() != nova_descricao
    )

    if not houve_mudanca:
        return False

    processo.ultima_movimentacao = nova_descricao
    processo.data_movimentacao = nova_data
    processo.tribunal = novo_tribunal

    existe_mov = MovimentacaoProcessual.query.filter_by(
        processo_id=processo.id,
        data=nova_data,
        descricao=nova_descricao
    ).first()

    if not existe_mov:
        nova = MovimentacaoProcessual(
            processo_id=processo.id,
            data=nova_data,
            descricao=nova_descricao,
            tribunal=novo_tribunal
        )
        db.session.add(nova)

    return True


def processo_esta_finalizado(processo):
    texto = (processo.ultima_movimentacao or "").lower()

    termos = ["arquivado", "definitivo", "baixado"]
    return any(t in texto for t in termos)


def atualizar_processos():
    processos = Processo.query.all()
    agora = datetime.now()

    for processo in processos:
        try:
            # ignora processos finalizados
            if processo_esta_finalizado(processo):
                continue

            # reduz frequência para processos muito antigos/parados
            if processo.data_movimentacao:
                try:
                    dias_sem_mov = (agora - processo.data_movimentacao).days
                except Exception:
                    dias_sem_mov = 0

                if dias_sem_mov > 90:
                    if processo.ultima_verificacao and (
                        agora - processo.ultima_verificacao < timedelta(days=1)
                    ):
                        continue

            detectou = verificar_nova_movimentacao(processo)

            processo.ultima_verificacao = agora

            db.session.commit()

            if detectou:
                print(f"🔥 DETECTOU MOVIMENTAÇÃO no processo {processo.numero}")

                mensagem = (
                    f"🚨 Nova movimentação!\n\n"
                    f"📁 Processo: {processo.numero}\n"
                    f"📌 {processo.ultima_movimentacao}"
                )

                cliente = Usuario.query.get(processo.cliente_id)
                advogado = Usuario.query.get(processo.advogado_id)

                print("Cliente telefone:", cliente.telefone if cliente else None)
                print("Advogado telefone:", advogado.telefone if advogado else None)

                if cliente and cliente.telefone:
                    try:
                        print("📤 Enviando para cliente...")
                        enviar_mensagem(cliente.telefone, mensagem)
                    except Exception as e:
                        print("❌ Erro ao enviar WhatsApp para cliente:", e)

                if advogado and advogado.telefone:
                    try:
                        print("📤 Enviando para advogado...")
                        enviar_mensagem(advogado.telefone, mensagem)
                    except Exception as e:
                        print("❌ Erro ao enviar WhatsApp para advogado:", e)

        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao monitorar processo {processo.numero}: {e}")