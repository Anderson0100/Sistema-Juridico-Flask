from flask import request, session, abort

from app import app
from core.auth import login_required
from models import SistemaLog
from services.db import db
from services.ia import responder_cliente
from services.whatsapp_service import enviar_mensagem
from services.chat_context import buscar_contexto_cliente
from utils.phone import limpar_numero
from utils.text import (
    normalizar_texto,
    eh_encerramento_curto,
    eh_pedido_humano,
    detectar_assunto_sensivel,
    resposta_insegura,
    eh_duvida_sobre_consulta,
)
from whatsapp.helpers import (
    obter_sessao,
    salvar_sessao,
    resetar_fluxo_menu,
    esta_em_modo_humano,
    adicionar_na_fila,
    total_na_fila,
    ativar_modo_humano,
    liberar_atendimento_humano,
    extrair_evento_id,
    evento_ja_processado,
)
from whatsapp.menu import (
    mensagem_menu_principal,
    mensagem_opcao_invalida,
    encaminhar_para_humano,
    corrigir_link_consulta,
    mensagem_consulta_portal,
    montar_contexto_seguro,
)


@app.route("/webhook/whatsapp", methods=["POST"])
def webhook_whatsapp():
    body = request.get_json(silent=True) or {}
    print("Recebido:", body)

    try:
        event = body.get("event", "")
        data = body.get("data", {}) or {}

        if event != "messages.upsert":
            return "ok", 200

        evento_id = extrair_evento_id(data)
        if evento_ja_processado(evento_id):
            print(f"Evento duplicado ignorado: {evento_id}")
            return "ok", 200

        key_data = data.get("key", {}) or {}
        msg = data.get("message", {}) or {}

        remote_jid = key_data.get("remoteJidAlt", "") or key_data.get("remoteJid", "")
        remote_jid = str(remote_jid or "").split(":")[0]
        from_me = key_data.get("fromMe", False)

        if from_me:
            return "ok", 200

        if "@g.us" in remote_jid:
            return "ok", 200

        if "status@broadcast" in remote_jid or "@broadcast" in remote_jid:
            return "ok", 200

        mensagem = ""
        tipo_msg = "desconhecido"

        if "conversation" in msg:
            mensagem = msg.get("conversation", "")
            tipo_msg = "texto"
        elif "extendedTextMessage" in msg:
            mensagem = msg.get("extendedTextMessage", {}).get("text", "")
            tipo_msg = "texto"
        elif "imageMessage" in msg:
            mensagem = msg.get("imageMessage", {}).get("caption", "") or "[imagem]"
            tipo_msg = "imagem"
        elif "videoMessage" in msg:
            mensagem = msg.get("videoMessage", {}).get("caption", "") or "[video]"
            tipo_msg = "video"
        elif "documentMessage" in msg:
            mensagem = msg.get("documentMessage", {}).get("fileName", "") or "[documento]"
            tipo_msg = "documento"
        else:
            return "ok", 200

        mensagem = (mensagem or "").strip()
        if not mensagem:
            return "ok", 200

        numero = limpar_numero(remote_jid.replace("@s.whatsapp.net", "").replace("@lid", ""))

        print("NUMERO:", numero)
        print("MENSAGEM:", mensagem)
        print("TIPO_MSG:", tipo_msg)

        sessao = obter_sessao(numero)

        if esta_em_modo_humano(numero) or sessao.get("modo_humano"):
            print(f"IA bloqueada para {numero} - atendimento humano ativo")
            return "ok", 200

        mensagem_lower = normalizar_texto(mensagem)

        if eh_encerramento_curto(mensagem):
            print(f"Mensagem curta ignorada: {mensagem_lower}")
            return "ok", 200

        contexto = buscar_contexto_cliente(numero, mensagem) or {}
        contexto = corrigir_link_consulta(contexto)

        if contexto.get("cliente_encontrado"):
            sessao["cliente_identificado"] = True
            sessao["nome_cliente"] = contexto.get("nome_cliente", "") or ""
            sessao["numero_processo"] = contexto.get("numero_processo", "") or ""

        # pedido humano em qualquer momento
        if eh_pedido_humano(mensagem):
            sessao["aguardando_opcao"] = False
            sessao["aguardando_assunto"] = True
            sessao["fluxo"] = "encaminhamento_humano"
            salvar_sessao(numero, sessao)

            enviar_mensagem(
                numero,
                "Perfeito.\n\nAntes de encaminhar, me informe brevemente o assunto do atendimento."
            )
            return "ok", 200

        # primeira interação -> menu
        if not sessao["apresentou_lia"]:
            sessao["apresentou_lia"] = True
            sessao = resetar_fluxo_menu(sessao)
            salvar_sessao(numero, sessao)
            enviar_mensagem(numero, mensagem_menu_principal())
            return "ok", 200

        # comandos de voltar
        if mensagem_lower in ["menu", "voltar", "inicio", "início"]:
            sessao = resetar_fluxo_menu(sessao)
            salvar_sessao(numero, sessao)
            enviar_mensagem(numero, mensagem_menu_principal())
            return "ok", 200

        # ==========================
        # MENU PRINCIPAL
        # ==========================
        if sessao.get("aguardando_opcao"):
            if mensagem_lower == "1":
                sessao["aguardando_opcao"] = False
                sessao["aguardando_assunto"] = True
                sessao["fluxo"] = "encaminhamento_humano"
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    "Perfeito.\n\nAntes de encaminhar, me informe brevemente o assunto do atendimento."
                )
                return "ok", 200

            elif mensagem_lower == "2":
                sessao["aguardando_opcao"] = False
                sessao["aguardando_cpf"] = True
                sessao["fluxo"] = "consultar_processo"
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    "Para localizar seu processo, me informe seu CPF.\n"
                    "Se preferir, você também pode enviar seu nome completo."
                )
                return "ok", 200

            elif mensagem_lower == "3":
                sessao["aguardando_opcao"] = False
                sessao["aguardando_nome"] = True
                sessao["fluxo"] = "cliente_novo"
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    "Perfeito. Me envie seu nome completo para eu iniciar seu atendimento."
                )
                return "ok", 200

            elif mensagem_lower == "4":
                sessao["aguardando_opcao"] = False
                sessao["aguardando_cpf"] = True
                sessao["fluxo"] = "como_consultar"
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    "Para eu te orientar melhor, me informe seu CPF.\n"
                    "Se preferir, você também pode enviar seu nome completo."
                )
                return "ok", 200

            elif mensagem_lower == "5":
                sessao["aguardando_opcao"] = False
                sessao["fluxo"] = "outras_duvidas"
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    "Claro. Me diga em uma frase qual é a sua dúvida."
                )
                return "ok", 200

            else:
                salvar_sessao(numero, sessao)
                enviar_mensagem(numero, mensagem_opcao_invalida())
                return "ok", 200

        # ==========================
        # FLUXO: ENCAMINHAMENTO HUMANO
        # ==========================
        if sessao.get("fluxo") == "encaminhamento_humano" and sessao.get("aguardando_assunto"):
            sessao["assunto_atendimento"] = mensagem.strip()
            sessao["aguardando_assunto"] = False

            ok = encaminhar_para_humano(
                numero=numero,
                mensagem=mensagem,
                contexto=contexto,
                assunto=sessao.get("assunto_atendimento", "")
            )

            posicao = adicionar_na_fila(
                numero=numero,
                nome=contexto.get("nome_cliente", "") or sessao.get("nome_cliente", ""),
                assunto=sessao.get("assunto_atendimento", "")
            )

            sessao["encaminhado_humano"] = True
            sessao["modo_humano"] = True
            salvar_sessao(numero, sessao)

            if ok:
                enviar_mensagem(
                    numero,
                    f"Perfeito. Seu atendimento foi encaminhado para a equipe do escritório.\n\n"
                    f"Assunto registrado: {sessao.get('assunto_atendimento')}\n"
                    f"Posição atual na fila: {posicao}\n"
                    f"Total aguardando: {total_na_fila()}\n\n"
                    f"A partir de agora, um responsável seguirá por aqui."
                )
            else:
                enviar_mensagem(
                    numero,
                    "Entendi. Houve um problema ao registrar o encaminhamento, mas sua solicitação foi anotada."
                )
            return "ok", 200

        # ==========================
        # FLUXO: CONSULTAR PROCESSO
        # ==========================
        if sessao.get("fluxo") == "consultar_processo":
            if contexto.get("cliente_encontrado") and contexto.get("numero_processo"):
                resposta = (
                    f"Localizei seu processo.\n\n"
                    f"Número:\n{contexto.get('numero_processo')}"
                )

                if contexto.get("tipo_movimentacao") == "sensivel":
                    resposta += "\n\nHouve uma atualização recente, mas os detalhes completos devem ser consultados no portal oficial."

                if contexto.get("consulta_url"):
                    resposta += f"\n\nConsulta oficial:\n{contexto.get('consulta_url')}"

                sessao["cliente_identificado"] = True
                sessao["numero_processo"] = contexto.get("numero_processo", "") or sessao.get("numero_processo", "")
                sessao["nome_cliente"] = contexto.get("nome_cliente", "") or sessao.get("nome_cliente", "")
                sessao["aguardando_opcao"] = False
                sessao["aguardando_cpf"] = False
                sessao["aguardando_nome"] = False
                sessao["fluxo"] = "pos_consulta"
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    resposta + "\n\nSe quiser, posso te explicar como consultar no portal oficial. Digite *menu* para voltar ao início."
                )
                return "ok", 200

            if not sessao.get("aguardando_nome"):
                sessao["aguardando_cpf"] = False
                sessao["aguardando_nome"] = True
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    "Ainda não consegui localizar seu cadastro por esse dado.\n"
                    "Me envie seu nome completo."
                )
                return "ok", 200

            assunto_registrado = "Cliente não localizado no sistema para consulta de processo"

            ok = encaminhar_para_humano(
                numero=numero,
                mensagem=mensagem,
                contexto=contexto,
                assunto=assunto_registrado
            )

            posicao = adicionar_na_fila(
                numero=numero,
                nome=sessao.get("nome_cliente", "") or "",
                assunto=assunto_registrado
            )

            sessao["assunto_atendimento"] = assunto_registrado
            sessao["encaminhado_humano"] = True
            sessao["modo_humano"] = True
            sessao["aguardando_nome"] = False
            sessao["aguardando_opcao"] = False
            sessao["fluxo"] = "encaminhamento_humano"
            salvar_sessao(numero, sessao)

            if ok:
                enviar_mensagem(
                    numero,
                    f"Não consegui localizar seu cadastro no sistema com segurança.\n\n"
                    f"Vou encaminhar seu atendimento para a equipe do escritório.\n"
                    f"Posição atual na fila: {posicao}\n"
                    f"Total aguardando: {total_na_fila()}"
                )
            else:
                enviar_mensagem(
                    numero,
                    "Não consegui localizar seu cadastro no sistema.\n"
                    "Sua solicitação foi registrada e a equipe do escritório seguirá por aqui."
                )

            return "ok", 200

        # ==========================
        # FLUXO: COMO CONSULTAR
        # ==========================
        if sessao.get("fluxo") == "como_consultar":
            if contexto.get("cliente_encontrado") and contexto.get("numero_processo"):
                resposta = mensagem_consulta_portal(contexto)

                if not resposta:
                    assunto_registrado = "Tribunal do processo não identificado para orientar consulta"

                    ok = encaminhar_para_humano(
                        numero=numero,
                        mensagem=mensagem,
                        contexto=contexto,
                        assunto=assunto_registrado
                    )

                    posicao = adicionar_na_fila(
                        numero=numero,
                        nome=sessao.get("nome_cliente", "") or "",
                        assunto=assunto_registrado
                    )

                    sessao["assunto_atendimento"] = assunto_registrado
                    sessao["encaminhado_humano"] = True
                    sessao["modo_humano"] = True
                    sessao["aguardando_nome"] = False
                    sessao["aguardando_opcao"] = False
                    sessao["fluxo"] = "encaminhamento_humano"
                    salvar_sessao(numero, sessao)

                    if ok:
                        enviar_mensagem(
                            numero,
                            f"Localizei seu processo, mas não consegui identificar com segurança o portal correto de consulta.\n\n"
                            f"Vou encaminhar seu atendimento para a equipe do escritório.\n"
                            f"Posição atual na fila: {posicao}\n"
                            f"Total aguardando: {total_na_fila()}"
                        )
                    else:
                        enviar_mensagem(
                            numero,
                            "Localizei seu processo, mas não consegui identificar com segurança o portal correto de consulta.\n"
                            "Sua solicitação foi registrada e a equipe do escritório seguirá por aqui."
                        )

                    return "ok", 200

                sessao["cliente_identificado"] = True
                sessao["numero_processo"] = contexto.get("numero_processo", "") or sessao.get("numero_processo", "")
                sessao["nome_cliente"] = contexto.get("nome_cliente", "") or sessao.get("nome_cliente", "")
                sessao["aguardando_opcao"] = False
                sessao["aguardando_cpf"] = False
                sessao["aguardando_nome"] = False
                sessao["fluxo"] = "pos_consulta"
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    resposta + "\n\nSe quiser, posso continuar te orientando sobre a consulta. Digite *menu* para voltar ao início."
                )
                return "ok", 200

            # ainda não achou -> pede nome uma vez
            if not sessao.get("aguardando_nome"):
                sessao["aguardando_cpf"] = False
                sessao["aguardando_nome"] = True
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    "Ainda não consegui localizar por esse dado.\n"
                    "Me envie seu nome completo para eu tentar localizar."
                )
                return "ok", 200

            # se já pediu nome e ainda não encontrou -> humano
            assunto_registrado = "Cliente não localizado no sistema para orientação de consulta do processo"

            ok = encaminhar_para_humano(
                numero=numero,
                mensagem=mensagem,
                contexto=contexto,
                assunto=assunto_registrado
            )

            posicao = adicionar_na_fila(
                numero=numero,
                nome=sessao.get("nome_cliente", "") or "",
                assunto=assunto_registrado
            )

            sessao["assunto_atendimento"] = assunto_registrado
            sessao["encaminhado_humano"] = True
            sessao["modo_humano"] = True
            sessao["aguardando_nome"] = False
            sessao["aguardando_opcao"] = False
            sessao["fluxo"] = "encaminhamento_humano"
            salvar_sessao(numero, sessao)

            if ok:
                enviar_mensagem(
                    numero,
                    f"Não consegui localizar seu cadastro no sistema com segurança.\n\n"
                    f"Vou encaminhar seu atendimento para a equipe do escritório.\n"
                    f"Posição atual na fila: {posicao}\n"
                    f"Total aguardando: {total_na_fila()}"
                )
            else:
                enviar_mensagem(
                    numero,
                    "Não consegui localizar seu cadastro no sistema.\n"
                    "Sua solicitação foi registrada e a equipe do escritório seguirá por aqui."
                )

            return "ok", 200

        # ==========================
        # FLUXO: PÓS-CONSULTA
        # ==========================
        if sessao.get("fluxo") == "pos_consulta":
            if eh_pedido_humano(mensagem):
                sessao["aguardando_assunto"] = True
                sessao["fluxo"] = "encaminhamento_humano"
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    "Perfeito.\n\nAntes de encaminhar, me informe brevemente o assunto do atendimento."
                )
                return "ok", 200

            if eh_duvida_sobre_consulta(mensagem):
                contexto_aux = dict(contexto or {})
                contexto_aux["numero_processo"] = contexto_aux.get("numero_processo") or sessao.get("numero_processo", "")
                contexto_aux["nome_cliente"] = contexto_aux.get("nome_cliente") or sessao.get("nome_cliente", "")
                contexto_aux["consulta_url"] = contexto_aux.get("consulta_url", "")

                resposta = mensagem_consulta_portal(contexto_aux)

                if not resposta:
                    assunto_registrado = "Tribunal do processo não identificado para orientar consulta"

                    ok = encaminhar_para_humano(
                        numero=numero,
                        mensagem=mensagem,
                        contexto=contexto_aux,
                        assunto=assunto_registrado
                    )

                    posicao = adicionar_na_fila(
                        numero=numero,
                        nome=sessao.get("nome_cliente", "") or "",
                        assunto=assunto_registrado
                    )

                    sessao["assunto_atendimento"] = assunto_registrado
                    sessao["encaminhado_humano"] = True
                    sessao["modo_humano"] = True
                    sessao["fluxo"] = "encaminhamento_humano"
                    salvar_sessao(numero, sessao)

                    if ok:
                        enviar_mensagem(
                            numero,
                            f"Localizei seu processo, mas não consegui identificar com segurança o portal correto de consulta.\n\n"
                            f"Vou encaminhar seu atendimento para a equipe do escritório.\n"
                            f"Posição atual na fila: {posicao}\n"
                            f"Total aguardando: {total_na_fila()}"
                        )
                    else:
                        enviar_mensagem(
                            numero,
                            "Localizei seu processo, mas não consegui identificar com segurança o portal correto de consulta.\n"
                            "Sua solicitação foi registrada e a equipe do escritório seguirá por aqui."
                        )

                    return "ok", 200

                salvar_sessao(numero, sessao)
                enviar_mensagem(
                    numero,
                    resposta + "\n\nSe precisar de mais alguma orientação, pode continuar por aqui. Para voltar ao menu, digite *menu*."
                )
                return "ok", 200

            # qualquer outra pergunta fora do tema -> volta ao menu
            sessao = resetar_fluxo_menu(sessao)
            salvar_sessao(numero, sessao)
            enviar_mensagem(numero, mensagem_menu_principal())
            return "ok", 200

        # ==========================
        # FLUXO: CLIENTE NOVO
        # ==========================
        if sessao.get("fluxo") == "cliente_novo":
            if sessao.get("aguardando_nome"):
                if len(mensagem.split()) < 3:
                    enviar_mensagem(
                        numero,
                        "Por favor, me envie seu nome completo."
                    )
                    return "ok", 200

                sessao["nome_cliente"] = mensagem.strip()
                sessao["aguardando_nome"] = False
                sessao["aguardando_resumo"] = True
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    "Perfeito.\n\nAgora me envie brevemente o assunto ou resumo do seu caso."
                )
                return "ok", 200

            if sessao.get("aguardando_resumo"):
                sessao["aguardando_resumo"] = False
                sessao["assunto_atendimento"] = mensagem.strip()

                posicao = adicionar_na_fila(
                    numero=numero,
                    nome=sessao.get("nome_cliente", ""),
                    assunto=sessao.get("assunto_atendimento", "")
                )

                ativar_modo_humano(numero)

                sessao["encaminhado_humano"] = True
                sessao["modo_humano"] = True
                salvar_sessao(numero, sessao)

                enviar_mensagem(
                    numero,
                    f"Perfeito. Já registrei seu atendimento.\n\n"
                    f"Assunto: {sessao.get('assunto_atendimento')}\n"
                    f"Posição atual na fila: {posicao}\n"
                    f"Total aguardando: {total_na_fila()}\n\n"
                    f"A partir de agora, a equipe do escritório seguirá por aqui."
                )
                return "ok", 200

        # ==========================
        # FLUXO: OUTRAS DÚVIDAS
        # ==========================
        if sessao.get("fluxo") == "outras_duvidas":
            contexto["primeira_interacao"] = False
            contexto["sugerir_humano"] = False
            contexto["atendimento_inicial"] = False

            contexto_seguro = montar_contexto_seguro(numero, mensagem, contexto)

            try:
                resposta = responder_cliente(mensagem, contexto_seguro)
            except Exception as e:
                print("Erro ao responder_cliente em outras_duvidas:", e)
                resposta = ""

            mensagem_normalizada = normalizar_texto(mensagem)

            pediu_humano_agora = eh_pedido_humano(mensagem)
            assunto_sensivel = detectar_assunto_sensivel(mensagem)
            ia_insegura = (not resposta) or resposta_insegura(resposta)

            # se for assunto delicado ou a IA estiver insegura, encaminha
            if pediu_humano_agora or assunto_sensivel or ia_insegura:
                assunto_registrado = mensagem[:150].strip()

                ok = encaminhar_para_humano(
                    numero=numero,
                    mensagem=mensagem,
                    contexto=contexto_seguro,
                    assunto=assunto_registrado
                )

                posicao = adicionar_na_fila(
                    numero=numero,
                    nome=contexto.get("nome_cliente", "") or sessao.get("nome_cliente", ""),
                    assunto=assunto_registrado
                )

                sessao["assunto_atendimento"] = assunto_registrado
                sessao["encaminhado_humano"] = True
                sessao["modo_humano"] = True
                sessao["aguardando_opcao"] = False
                sessao["fluxo"] = "encaminhamento_humano"
                salvar_sessao(numero, sessao)

                texto_encaminhamento = (
                    "Entendi. Para te orientar com mais segurança, vou encaminhar seu atendimento para a equipe do escritório.\n\n"
                    f"Assunto registrado: {assunto_registrado}\n"
                    f"Posição atual na fila: {posicao}\n"
                    f"Total aguardando: {total_na_fila()}\n\n"
                    "A equipe continuará o atendimento por aqui."
                )

                if not ok:
                    texto_encaminhamento = (
                        "Entendi. Não consegui concluir a resposta com segurança.\n"
                        "Sua solicitação foi registrada e a equipe do escritório seguirá por aqui."
                    )

                enviar_mensagem(numero, texto_encaminhamento)
                return "ok", 200

            # mantém a conversa ativa, sem resetar para o menu
            sessao["aguardando_opcao"] = False
            sessao["fluxo"] = "outras_duvidas"
            salvar_sessao(numero, sessao)

            enviar_mensagem(
                numero,
                f"{resposta}\n\nSe quiser, pode me explicar melhor.\nDigite *menu* para voltar ao início."
            )
            return "ok", 200

        # fallback
        sessao = resetar_fluxo_menu(sessao)
        salvar_sessao(numero, sessao)
        enviar_mensagem(numero, mensagem_menu_principal())

    except Exception as e:
        print("Erro webhook:", repr(e))

    return "ok", 200
  
  
@app.route("/whatsapp/liberar-humano", methods=["POST"])
@login_required()
def liberar_modo_humano_rota():
    if session.get("usuario_tipo") not in ["admin", "advogado"]:
        abort(403)

    payload = request.get_json(silent=True) or {}
    numero = request.form.get("numero") or payload.get("numero", "")
    numero = limpar_numero(numero)

    if not numero:
        return {"ok": False, "erro": "Número não informado"}, 400

    ok = liberar_atendimento_humano(numero)

    if ok:
        db.session.add(SistemaLog(
            usuario_id=session.get("usuario_id"),
            usuario_nome=session.get("usuario_nome", "Sistema"),
            acao=f"Modo humano liberado manualmente para o número {numero}"
        ))
        db.session.commit()
        return {"ok": True, "mensagem": f"Modo humano liberado para {numero}"}, 200

    return {"ok": False, "erro": "Não foi possível liberar o modo humano"}, 400
  