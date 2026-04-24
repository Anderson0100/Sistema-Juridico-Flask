from models import SistemaLog
from services.db import db
from utils.text import normalizar_texto
from whatsapp.helpers import ativar_modo_humano


TRIBUNAIS_CONSULTA = {
    "tjba": {
        "nome": "TJBA",
        "consulta_url": "https://esaj.tjba.jus.br/cpopg/open.do"
    },
    "trf1": {
        "nome": "TRF1",
        "consulta_url": "https://processual.trf1.jus.br/consultaProcessual/"
    },
    "trt5": {
        "nome": "TRT5",
        "consulta_url": "https://pje.trt5.jus.br/consultaprocessual/"
    }
}


def mensagem_menu_principal():
    return (
        "Olá, eu sou a Lia, do atendimento do escritório.\n\n"
        "Digite o número da opção desejada:\n\n"
        "1. Falar com a equipe do escritório\n"
        "2. Consultar meu processo\n"
        "3. Sou cliente novo\n"
        "4. Como consultar meu processo\n"
        "5. Outras dúvidas"
    )


def mensagem_opcao_invalida():
    return (
        "Não entendi a opção escolhida.\n\n"
        "Por favor, responda com o número da opção desejada:\n\n"
        "1. Falar com a equipe do escritório\n"
        "2. Consultar meu processo\n"
        "3. Sou cliente novo\n"
        "4. Como consultar meu processo\n"
        "5. Outras dúvidas"
    )


def detectar_tribunal_por_numero(numero_processo):
    numero = (numero_processo or "").strip()

    if ".4.01." in numero:
        return "trf1"
    elif ".5.05." in numero:
        return "trt5"
    elif ".8.05." in numero:
        return "tjba"

    return None


def corrigir_link_consulta(contexto):
    numero_processo = (contexto.get("numero_processo", "") or "").strip()
    tribunal_nome_ctx = normalizar_texto(contexto.get("tribunal_nome", ""))
    tribunal_codigo_ctx = normalizar_texto(contexto.get("tribunal_codigo", ""))
    link_ctx = (contexto.get("consulta_url", "") or "").strip()

    tribunal_detectado = detectar_tribunal_por_numero(numero_processo)

    if tribunal_detectado and tribunal_detectado in TRIBUNAIS_CONSULTA:
        contexto["tribunal_nome"] = TRIBUNAIS_CONSULTA[tribunal_detectado]["nome"]
        if not link_ctx:
            contexto["consulta_url"] = TRIBUNAIS_CONSULTA[tribunal_detectado]["consulta_url"]
        return contexto

    if "tjba" in tribunal_nome_ctx or "tjba" in tribunal_codigo_ctx or "bahia" in tribunal_nome_ctx:
        contexto["tribunal_nome"] = "TJBA"
        if not link_ctx:
            contexto["consulta_url"] = TRIBUNAIS_CONSULTA["tjba"]["consulta_url"]
        return contexto

    if "trf1" in tribunal_nome_ctx:
        contexto["tribunal_nome"] = "TRF1"
        if not link_ctx:
            contexto["consulta_url"] = TRIBUNAIS_CONSULTA["trf1"]["consulta_url"]
        return contexto

    if "trt5" in tribunal_nome_ctx:
        contexto["tribunal_nome"] = "TRT5"
        if not link_ctx:
            contexto["consulta_url"] = TRIBUNAIS_CONSULTA["trt5"]["consulta_url"]
        return contexto

    return contexto


def mensagem_consulta_portal(contexto):
    numero_processo = (contexto.get("numero_processo", "") or "").strip()
    tribunal_nome = (contexto.get("tribunal_nome", "") or "").strip()
    link = (contexto.get("consulta_url", "") or "").strip()

    if not tribunal_nome or not link:
        tribunal_detectado = detectar_tribunal_por_numero(numero_processo)
        if tribunal_detectado and tribunal_detectado in TRIBUNAIS_CONSULTA:
            tribunal_nome = TRIBUNAIS_CONSULTA[tribunal_detectado]["nome"]
            link = TRIBUNAIS_CONSULTA[tribunal_detectado]["consulta_url"]

    if not tribunal_nome or not link:
        return None

    return (
        f"Claro. Vou te explicar de forma simples.\n\n"
        f"1. Acesse o portal oficial do {tribunal_nome}:\n"
        f"{link}\n\n"
        f"2. Entre na área de consulta processual.\n"
        f"3. Digite o número do processo:\n"
        f"{numero_processo}\n\n"
        f"4. Confira o andamento e as movimentações."
    )


def montar_contexto_seguro(numero, mensagem, contexto):
    nome_cliente = (contexto.get("nome_cliente", "") or "").strip()
    numero_processo = (contexto.get("numero_processo", "") or "").strip()

    return {
        "numero": numero,
        "mensagem": mensagem,
        "nome_cliente": nome_cliente,
        "numero_processo": numero_processo,
        "cliente_encontrado": bool(contexto.get("cliente_encontrado")),
        "tribunal_nome": contexto.get("tribunal_nome", ""),
        "consulta_url": contexto.get("consulta_url", "")
    }


def encaminhar_para_humano(numero, mensagem, contexto, assunto=""):
    try:
        nome_cliente = contexto.get("nome_cliente", "") or ""
        numero_processo = contexto.get("numero_processo", "") or ""

        db.session.add(SistemaLog(
            usuario_id=None,
            usuario_nome="Sistema",
            acao=(
                f"Atendimento humano solicitado via WhatsApp. "
                f"Número: {numero}. "
                f"Cliente: {nome_cliente or 'Não identificado'}. "
                f"Processo: {numero_processo or 'Não informado'}. "
                f"Assunto: {assunto or 'Não informado'}. "
                f"Mensagem: {mensagem}"
            )
        ))
        db.session.commit()

        ativar_modo_humano(numero)
        return True

    except Exception as e:
        print("Erro ao encaminhar para humano:", e)
        return False