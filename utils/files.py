import json
import os


def arquivo_permitido(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def allowed_file(file):
    filename = (file.filename or "").lower()

    if not filename.endswith(".pdf"):
        return False

    mime = file.mimetype
    if mime != "application/pdf":
        return False

    return True


def carregar_json_seguro(caminho, default):
    if not os.path.exists(caminho):
        return default

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar {caminho}:", e)
        return default


def salvar_json_seguro(caminho, conteudo):
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(conteudo, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar {caminho}:", e)