import re
from models import Usuario, Processo
from services.consulta import consultar_processo
from services.tribunal_detector import obter_info_tribunal


def normalizar_numero(numero):
    if not numero:
        return ""
    return "".join(ch for ch in str(numero) if ch.isdigit())


def normalizar_nome(nome):
    if not nome:
        return ""
    nome = str(nome).strip().lower()
    nome = " ".join(nome.split())
    return nome


def formatar_data(dt):
    if not dt:
        return ""
    try:
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


def extrair_cpf(texto):
    if not texto:
        return None

    cpf = re.sub(r"\D", "", texto)
    if len(cpf) == 11:
        return cpf

    return None


def extrair_numero_processo(texto):
    if not texto:
        return None

    numeros = re.sub(r"\D", "", texto)

    # CNJ costuma ter 20 dígitos sem máscara
    if len(numeros) >= 20:
        return numeros[:20]

    return None


def classificar_movimentacao(texto):
    if not texto:
        return "desconhecida"

    t = texto.lower()

    palavras_audiencia = [
        "audiência",
        "audiencia",
        "sessão",
        "sessao",
        "designada audiência",
        "designada audiencia",
        "marcada audiência",
        "marcada audiencia",
        "ato ordinatório de audiência",
        "ato ordinatorio de audiencia",
    ]

    palavras_sensiveis = [
        "decurso de prazo",
        "prazo decorrido",
        "intempestivo",
        "perda de prazo",
        "arquivado",
        "extinto",
        "indeferido",
        "negado",
        "improcedente",
        "sentença",
        "sentenca",
        "julgado",
        "trânsito em julgado",
        "transito em julgado",
        "baixa definitiva",
        "cumprimento de sentença",
        "cumprimento de sentenca",
    ]

    for palavra in palavras_audiencia:
        if palavra in t:
            return "audiencia"

    for palavra in palavras_sensiveis:
        if palavra in t:
            return "sensivel"

    return "segura"


def movimentacao_publica(texto, tipo):
    if not texto:
        return ""

    if tipo == "sensivel":
        return ""

    return texto


def montar_contexto_vazio():
    return {
        "cliente_encontrado": False,
        "nome_cliente": "",
        "numero_processo": "",
        "tribunal_codigo": "",
        "tribunal_nome": "",
        "consulta_url": "",
        "ultima_movimentacao": "",
        "tipo_movimentacao": "desconhecida",
        "data_movimentacao": "",
        "tem_multiplos_processos": False
    }


def buscar_cliente_por_whatsapp(numero_whatsapp):
    numero_limpo = normalizar_numero(numero_whatsapp)

    if not numero_limpo:
        return None

    clientes = Usuario.query.filter_by(tipo="cliente").all()

    for cliente in clientes:
        telefone = normalizar_numero(cliente.telefone or "")

        if not telefone:
            continue

        if telefone == numero_limpo:
            return cliente

        if len(telefone) >= 8 and len(numero_limpo) >= 8:
            if telefone[-8:] == numero_limpo[-8:]:
                return cliente

        if telefone in numero_limpo or numero_limpo in telefone:
            return cliente

    return None


def buscar_cliente_por_cpf(texto):
    cpf = extrair_cpf(texto)
    if not cpf:
        return None

    return Usuario.query.filter_by(tipo="cliente", cpf=cpf).first()


def buscar_cliente_por_nome(texto):
    nome_msg = normalizar_nome(texto)

    if not nome_msg or len(nome_msg) < 3:
        return None

    clientes = Usuario.query.filter_by(tipo="cliente").all()

    # 1. igualdade exata
    for cliente in clientes:
        nome_cliente = normalizar_nome(cliente.nome)
        if nome_cliente == nome_msg:
            return cliente

    # 2. correspondência parcial
    for cliente in clientes:
        nome_cliente = normalizar_nome(cliente.nome)
        if nome_msg in nome_cliente or nome_cliente in nome_msg:
            return cliente

    # 3. aproximação por partes do nome
    partes_msg = [p for p in nome_msg.split() if len(p) >= 3]

    if len(partes_msg) >= 2:
        for cliente in clientes:
            nome_cliente = normalizar_nome(cliente.nome)
            acertos = sum(1 for p in partes_msg if p in nome_cliente)

            if acertos >= max(2, len(partes_msg) - 1):
                return cliente

    return None


def buscar_processo_por_numero(cliente_id, mensagem):
    numero_extraido = extrair_numero_processo(mensagem)
    if not numero_extraido:
        return None

    processos = Processo.query.filter_by(cliente_id=cliente_id).all()

    for processo in processos:
        numero_proc = normalizar_numero(processo.numero)
        if numero_proc == numero_extraido:
            return processo

    return None


def buscar_processo_principal(cliente_id):
    return (
        Processo.query
        .filter_by(cliente_id=cliente_id)
        .order_by(Processo.id.desc())
        .first()
    )


def enriquecer_dados_processo(processo):
    tribunal_nome = ""
    consulta_url = ""
    ultima_movimentacao = processo.ultima_movimentacao or ""
    data_movimentacao = formatar_data(processo.data_movimentacao)

    dados_consulta = None

    try:
        dados_consulta = consultar_processo(processo.numero)
    except Exception as e:
        print("Erro ao consultar processo externamente:", e)

    if dados_consulta:
        processo.tribunal = dados_consulta.get("tribunal") or processo.tribunal
        processo.ultima_movimentacao = (
            dados_consulta.get("ultima_movimentacao") or processo.ultima_movimentacao
        )
        processo.data_movimentacao = dados_consulta.get("data") or processo.data_movimentacao

        tribunal_nome = dados_consulta.get("tribunal_nome", "") or ""
        consulta_url = dados_consulta.get("consulta_url", "") or ""
        ultima_movimentacao = dados_consulta.get("ultima_movimentacao") or ultima_movimentacao
        data_movimentacao = formatar_data(dados_consulta.get("data")) or data_movimentacao
    else:
        info = obter_info_tribunal(processo.tribunal) if processo.tribunal else None
        if info:
            tribunal_nome = info.get("nome", "") or ""
            consulta_url = info.get("consulta_url", "") or ""

    tipo_movimentacao = classificar_movimentacao(ultima_movimentacao)
    ultima_movimentacao_publica = movimentacao_publica(ultima_movimentacao, tipo_movimentacao)

    return {
        "tribunal_codigo": processo.tribunal or "",
        "tribunal_nome": tribunal_nome,
        "consulta_url": consulta_url,
        "ultima_movimentacao": ultima_movimentacao_publica or "",
        "tipo_movimentacao": tipo_movimentacao,
        "data_movimentacao": data_movimentacao or "",
    }


def montar_contexto_cliente(cliente, mensagem=None):
    if not cliente:
        return montar_contexto_vazio()

    processos_cliente = Processo.query.filter_by(cliente_id=cliente.id).all()

    processo = None

    if mensagem:
        processo = buscar_processo_por_numero(cliente.id, mensagem)

    if not processo:
        processo = buscar_processo_principal(cliente.id)

    if not processo:
        return {
            "cliente_encontrado": True,
            "nome_cliente": cliente.nome or "",
            "numero_processo": "",
            "tribunal_codigo": "",
            "tribunal_nome": "",
            "consulta_url": "",
            "ultima_movimentacao": "",
            "tipo_movimentacao": "desconhecida",
            "data_movimentacao": "",
            "tem_multiplos_processos": False
        }

    dados = enriquecer_dados_processo(processo)

    return {
        "cliente_encontrado": True,
        "nome_cliente": cliente.nome or "",
        "numero_processo": processo.numero or "",
        "tribunal_codigo": dados["tribunal_codigo"],
        "tribunal_nome": dados["tribunal_nome"],
        "consulta_url": dados["consulta_url"],
        "ultima_movimentacao": dados["ultima_movimentacao"],
        "tipo_movimentacao": dados["tipo_movimentacao"],
        "data_movimentacao": dados["data_movimentacao"],
        "tem_multiplos_processos": len(processos_cliente) > 1
    }


def buscar_contexto_cliente(numero_whatsapp, mensagem=None):
    mensagem = (mensagem or "").strip()

    # prioridade:
    # 1. telefone do WhatsApp
    # 2. CPF digitado
    # 3. nome completo
    cliente = buscar_cliente_por_whatsapp(numero_whatsapp)

    if not cliente and mensagem:
        cliente = buscar_cliente_por_cpf(mensagem)

    if not cliente and mensagem:
        cliente = buscar_cliente_por_nome(mensagem)

    return montar_contexto_cliente(cliente, mensagem)