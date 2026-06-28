import os
import requests

from datetime import datetime, timezone
from services.tribunal_detector import detectar_tribunal, obter_info_tribunal

DATAJUD_BASE = "https://api-publica.datajud.cnj.jus.br"
API_KEY = (os.getenv("DATAJUD_API_KEY") or "").strip()

HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "Content-Type": "application/json"
}


def converter_data(data_str):
    if not data_str:
        return None

    try:
        data = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        if data.tzinfo:
            data = data.astimezone(timezone.utc).replace(tzinfo=None)
        return data
    except Exception:
        return None


def montar_url_datajud(codigo_tribunal):
    info = obter_info_tribunal(codigo_tribunal)
    if not info:
        return None

    alias = info.get("alias")
    if not alias:
        return None

    return f"{DATAJUD_BASE}/{alias}/_search"


def extrair_hit_mais_recente(hits):
    if not hits:
        return None

    melhor_hit = None
    melhor_data = None

    for item in hits:
        source = item.get("_source", {}) or {}

        data_mov = (
            source.get("dataHoraUltimaAtualizacao")
            or source.get("dataUltimaAtualizacao")
            or source.get("dataAjuizamento")
        )

        data_convertida = converter_data(data_mov)

        if melhor_hit is None:
            melhor_hit = item
            melhor_data = data_convertida
            continue

        if data_convertida and (melhor_data is None or data_convertida > melhor_data):
            melhor_hit = item
            melhor_data = data_convertida

    return melhor_hit


def extrair_movimentacao(hit):
    if not hit:
        return None

    source = hit.get("_source", {}) or {}

    movimentacoes = source.get("movimentos", []) or []

    ultima_movimentacao = "Sem movimentações encontradas"
    data_movimentacao = None

    if movimentacoes:
        movimento_recente = None
        data_recente = None

        for mov in movimentacoes:
            data_mov = mov.get("dataHora") or mov.get("data")
            data_convertida = converter_data(data_mov)

            if movimento_recente is None:
                movimento_recente = mov
                data_recente = data_convertida
                continue

            if data_convertida and (data_recente is None or data_convertida > data_recente):
                movimento_recente = mov
                data_recente = data_convertida

        if movimento_recente:
            ultima_movimentacao = (
                movimento_recente.get("nome")
                or movimento_recente.get("descricao")
                or movimento_recente.get("codigo")
                or "Movimentação localizada"
            )
            data_movimentacao = converter_data(
                movimento_recente.get("dataHora")
                or movimento_recente.get("data")
            )

    tribunal = (
        source.get("tribunal")
        or source.get("orgaoJulgador", {}).get("nome")
        or source.get("grau")
        or ""
    )

    return {
        "ultima_movimentacao": ultima_movimentacao,
        "data": data_movimentacao,
        "tribunal": tribunal
    }


def consultar_processo(numero_processo):
    numero_processo = (numero_processo or "").strip()

    if not numero_processo:
        print("DataJud: número do processo vazio.")
        return None

    if not API_KEY:
        print("DataJud: DATAJUD_API_KEY não encontrada no ambiente.")
        return None

    codigo_tribunal = detectar_tribunal(numero_processo)

    if not codigo_tribunal:
        print(f"Tribunal não detectado para o processo {numero_processo}")
        return None

    info_tribunal = obter_info_tribunal(codigo_tribunal)

    if not info_tribunal:
        print(f"DataJud: informações do tribunal não encontradas para {codigo_tribunal}")
        return None

    url = montar_url_datajud(codigo_tribunal)

    if not url:
        print(f"DataJud: URL não montada para o tribunal {codigo_tribunal}")
        return None

    payload = {
        "query": {
            "term": {
                "numeroProcesso.keyword": numero_processo
            }
        },
        "sort": [
            {
                "dataHoraUltimaAtualizacao": {
                    "order": "desc"
                }
            }
        ],
        "size": 1
    }

    try:
        print("===================================")
        print("DataJud: iniciando consulta")
        print("Processo:", numero_processo)
        print("Tribunal detectado:", codigo_tribunal)
        print("Nome tribunal:", info_tribunal.get("nome"))
        print("URL final:", url)
        print("API key carregada?:", bool(API_KEY))
        print("Tamanho da key:", len(API_KEY))
        print("===================================")

        response = requests.post(
            url,
            headers=HEADERS,
            json=payload,
            timeout=30
        )

        print("STATUS CODE:", response.status_code)

        if response.status_code == 401:
            print("Erro DataJud 401:", response.text)
            return None

        if response.status_code >= 400:
            print("Erro DataJud:", response.text)
            return None

        dados = response.json()

        hits = (((dados.get("hits") or {}).get("hits")) or [])

        if not hits:
            print(f"DataJud: nenhum resultado para o processo {numero_processo}")
            return None

        hit = extrair_hit_mais_recente(hits)
        resultado = extrair_movimentacao(hit)

        if not resultado:
            print(f"DataJud: resultado vazio para o processo {numero_processo}")
            return None

        if not resultado.get("tribunal"):
            resultado["tribunal"] = info_tribunal.get("nome", "")

        print("DataJud: consulta concluída com sucesso.")
        print("Última movimentação:", resultado.get("ultima_movimentacao"))
        print("Data:", resultado.get("data"))
        print("Tribunal:", resultado.get("tribunal"))

        return resultado

    except requests.exceptions.Timeout:
        print(f"DataJud: timeout ao consultar o processo {numero_processo}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"DataJud: erro de conexão ao consultar {numero_processo}: {e}")
        return None

    except Exception as e:
        print(f"DataJud: erro inesperado ao consultar {numero_processo}: {e}")
        return None
