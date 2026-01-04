import os
import re
import uuid
import mimetypes
import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
from datetime import timedelta
from datetime import datetime 
from google_calendar import get_auth_url, save_token, get_calendar_service, criar_evento_google
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# ==========================
# CONFIGURAÇÃO
# ==========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}

def arquivo_permitido(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

print("DATABASE_URL =", DATABASE_URL)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não foi carregado do .env")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024   # 5MB por arquivo
import secrets
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False  # Troca para True quando for HTTPS
)


os.makedirs(UPLOAD_FOLDER, exist_ok=True)
db = SQLAlchemy(app)

# ==========================
# MODELOS
# ==========================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True)
    cpf = db.Column(db.String(11), unique=True)
    data_nascimento = db.Column(db.String(10))
    senha = db.Column(db.String(200))
    tipo = db.Column(db.String(20), nullable=False)
    ativo = db.Column(db.Boolean, default=True)

    advogado_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    advogado = db.relationship("Usuario", remote_side=[id])

    # RELAÇÕES EXPLÍCITAS
    processos_como_advogado = db.relationship(
        "Processo",
        foreign_keys="Processo.advogado_id",
        backref="advogado_rel",
        lazy=True
    )

    processos_como_cliente = db.relationship(
        "Processo",
        foreign_keys="Processo.cliente_id",
        backref="cliente_rel",
        lazy=True
    )

    processos_criados = db.relationship(
        "Processo",
        foreign_keys="Processo.criado_por",
        backref="criador_rel",
        lazy=True
    )

from datetime import datetime, timedelta

def agora_br():
    return datetime.utcnow() - timedelta(hours=3)

class Processo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Em andamento')
    prioridade = db.Column(db.String(20), default='Normal')
    descricao = db.Column(db.Text)
    data_criacao = db.Column(db.DateTime, default=agora_br)

    prazos = db.relationship('Prazo', backref='processo', lazy=True)

    data_audiencia = db.Column(db.String(10))
    hora_audiencia = db.Column(db.String(5))
    google_event_id = db.Column(db.String(255))

    advogado_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))   # quem é responsável
    criado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))   # quem criou
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    advogado = db.relationship("Usuario", foreign_keys=[advogado_id])
    criador = db.relationship("Usuario", foreign_keys=[criado_por])
    observacoes = db.relationship("Observacao", backref="processo_rel", lazy=True)


    cliente = db.relationship('Usuario', foreign_keys=[cliente_id])


class ProcessoArquivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_original = db.Column(db.String(200))
    nome_arquivo = db.Column(db.String(200))
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))


class ProcessoTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50))
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))

class ProcessoHistorico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    acao = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=agora_br)   # 👈 horário local do servidor
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

    usuario = db.relationship("Usuario")


class SistemaLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer)
    usuario_nome = db.Column(db.String(150))
    acao = db.Column(db.String(300))
    data = db.Column(db.DateTime, default=agora_br)


class NotificacaoCliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    mensagem = db.Column(db.String(300))
    lida = db.Column(db.Boolean, default=False)
    data = db.Column(db.DateTime, default=agora_br)

class Prazo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Aberto')  # Aberto, Cumprido, Vencido
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))
    titulo = db.Column(db.String(150))


class Historico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.now)
    acao = db.Column(db.String(200))

    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))


class Observacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    texto = db.Column(db.Text, nullable=False)
    data = db.Column(db.DateTime, default=agora_br)

    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'), nullable=False)
    advogado_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    advogado = db.relationship("Usuario")
    processo = db.relationship("Processo")

# ==========================
# FUNÇÕES AUXILIARES
# ==========================
def log_sistema(acao):
    if "usuario_id" in session:
        db.session.add(SistemaLog(
            usuario_id=session["usuario_id"],
            usuario_nome=session["usuario_nome"],
            acao=acao
        ))
        db.session.commit()

def validar_cpf(cpf):
    cpf = re.sub(r'\D', '', cpf)
    return len(cpf) == 11

def allowed_file(file):
    filename = file.filename.lower()

    if not filename.endswith(".pdf"):
        return False

    # Validação real do tipo do arquivo
    mime = file.mimetype
    if mime != "application/pdf":
        return False

    return True


def login_required(tipo=None):
    def decorator(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if 'usuario_id' not in session:
                return redirect(url_for('login'))
            if tipo and session.get('usuario_tipo') != tipo:
                flash('Acesso negado', 'danger')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrap
    return decorator

def pode_editar_processo(processo):
    return (
        session["usuario_tipo"] == "admin" or
        (session["usuario_tipo"] == "advogado" and processo.advogado_id == session["usuario_id"])
    )


# ==========================
# LOGIN
# ==========================
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        tipo = request.form['tipo']

        if tipo in ['admin', 'advogado']:
            user = Usuario.query.filter_by(
                email=request.form['email'],
                tipo=tipo
            ).first()

            if user and check_password_hash(user.senha, request.form['senha']):
                if not user.ativo:
                    flash("Conta desativada pelo administrador", "danger")
                    return redirect(url_for("login"))

                session.update({
                    'usuario_id': user.id,
                    'usuario_nome': user.nome,
                    'usuario_tipo': user.tipo
                })
                if user.tipo == "admin":
                    return redirect(url_for("painel_admin"))
                else:
                    return redirect(url_for("painel_advogado"))

            flash('Login inválido', 'danger')

        elif tipo == 'cliente':
            cpf = re.sub(r'\D', '', request.form['cpf'])
            user = Usuario.query.filter_by(
                cpf=cpf,
                data_nascimento=request.form['data_nascimento'],
                tipo='cliente'
            ).first()

            if user:
                session.update({
                    'usuario_id': user.id,
                    'usuario_nome': user.nome,
                    'usuario_tipo': user.tipo
                })
                return redirect(url_for('painel_cliente'))

            flash('Dados inválidos', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


from google_calendar import  get_calendar_service
 
@app.route("/google/login")
def google_login():
    url = get_auth_url()
    return redirect(url)


@app.route("/google/callback")
def google_callback():
    code = request.args.get("code")

    if not code:
        return "Erro ao autenticar com Google", 400

    save_token(code)
    return redirect(url_for("painel_advogado"))

 
@app.route('/conectar-google')
@login_required('advogado')
def conectar_google():
    from google_calendar import get_auth_url
    return redirect(get_auth_url())


@app.route("/processo/<int:id>/prazo", methods=["POST"], endpoint="adicionar_prazo")
@login_required()
def adicionar_prazo(id):
    processo = Processo.query.get_or_404(id)

    if not pode_editar_processo(processo):
        flash("Você não tem permissão para adicionar prazo neste processo", "danger")
        return redirect(url_for("detalhe_processo", id=id))

    titulo = request.form["titulo"]
    data = datetime.strptime(request.form["data"], "%Y-%m-%d").date()

    prazo = Prazo(
        titulo=titulo,
        descricao=titulo,              # 👈 obrigatório no banco
        data_vencimento=data,          # 👈 nome correto da coluna
        status="Aberto",
        processo_id=id
    )

    db.session.add(prazo)

    db.session.add(ProcessoHistorico(
        processo_id=id,
        acao=f"Prazo criado: {titulo} ({data.strftime('%d/%m/%Y')})"
    ))

    db.session.commit()

    return redirect(url_for("detalhe_processo", id=id))


@app.route("/prazo/<int:id>/excluir", methods=["POST"])
@login_required()
def excluir_prazo(id):
    prazo = Prazo.query.get_or_404(id)
    processo_id = prazo.processo_id

    db.session.add(Historico(
        processo_id=processo_id,
        acao=f"Prazo excluído: {prazo.titulo}"
    ))

    db.session.delete(prazo)
    db.session.commit()

    return redirect(url_for("detalhe_processo", id=processo_id))


@app.route("/advogado/audiencias")
@login_required
def lista_audiencias():
    audiencias = Audiencia.query.order_by(Audiencia.data, Audiencia.hora).all()
    return render_template("audiencias.html", audiencias=audiencias)

# ==========================
# CLIENTES – ADVOGADO (ROTAS MÍNIMAS)
# ==========================

@app.route('/advogado/clientes')
@login_required('advogado')
def clientes_advogado():
    advogado_id = session["usuario_id"]

    clientes = Usuario.query.filter_by(
        tipo="cliente",
        advogado_id=advogado_id
    ).all()

    return render_template("clientes.html", clientes=clientes)


@app.route('/advogado/clientes/novo', methods=['GET','POST'])
@login_required('advogado')
def novo_cliente():
    if request.method == 'POST':
        cpf = re.sub(r'\D','', request.form['cpf'])

        # Verifica CPF duplicado
        if Usuario.query.filter_by(cpf=cpf).first():
            flash("Já existe um cliente com esse CPF", "danger")
            return redirect(url_for("novo_cliente"))

        senha_temp = "123456"

        cliente = Usuario(
            nome=request.form['nome'],
            cpf=cpf,
            data_nascimento=request.form['data_nascimento'],
            email=request.form.get('email'),
            senha=generate_password_hash(senha_temp),
            tipo='cliente',
            advogado_id=session["usuario_id"]   # 👈 AQUI está a chave
        )

        db.session.add(cliente)
        db.session.commit()

        flash(f'Cliente criado! Senha inicial: {senha_temp}', 'success')
        return redirect(url_for('clientes_advogado'))

    return render_template('cliente_novo.html')


@app.route('/advogado/clientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required('advogado')
def editar_cliente(id):
    cliente = Usuario.query.get_or_404(id)

    # 🔐 Só pode editar se o cliente for dele
    if session["usuario_tipo"] != "admin" and cliente.advogado_id != session["usuario_id"]:
        abort(403)



    if request.method == "POST":
        cliente.nome = request.form["nome"]
        cliente.data_nascimento = request.form["data_nascimento"]
        db.session.commit()

        flash("Cliente atualizado com sucesso", "success")
        return redirect(url_for("clientes_advogado"))

    return render_template("cliente_editar.html", cliente=cliente)

@app.route('/processos/<int:id>/observacao', methods=['POST'])
@login_required('advogado')
def adicionar_observacao(id):
    processo = Processo.query.get_or_404(id)

    texto = request.form['texto']

    nova = Observacao(
        texto=texto,
        processo_id=processo.id,
        advogado_id=session['usuario_id']
    )

    db.session.add(nova)

    # histórico
    db.session.add(ProcessoHistorico(
        processo_id=id,
        usuario_id=session["usuario_id"],
        acao="Observação adicionada"
    ))


    db.session.commit()

    flash("Observação adicionada com sucesso", "success")
    return redirect(url_for('detalhe_processo', id=id))


from datetime import date

from datetime import date

from google_calendar import get_calendar_service

from datetime import date, timedelta

from datetime import date, timedelta, datetime
from flask import request
# ==========================
# PAINEL ADVOGADO
# ==========================
@app.route('/painel/advogado')
@login_required('advogado')
def painel_advogado():

    advogado_id = session['usuario_id']
    hoje = date.today()
    amanha = hoje + timedelta(days=1)
    q = request.args.get("q", "").strip()

    # ============================
    # AUDIÊNCIAS (próximas)
    # ============================
    audiencias = Processo.query.filter(
        Processo.advogado_id == advogado_id,
        Processo.data_audiencia != None,
        Processo.data_audiencia >= hoje.strftime("%Y-%m-%d")
    ).order_by(Processo.data_audiencia.asc()).limit(5).all()

    # ============================
    # GOOGLE CALENDAR
    # ============================
    service = get_calendar_service()
    google_conectado = True if service else False

    # ============================
    # PRAZOS
    # ============================
    prazos = Prazo.query.join(Processo).filter(
        Processo.advogado_id == advogado_id
    ).order_by(Prazo.data_vencimento.asc()).all()

    # ============================
    # ALERTAS INTELIGENTES
    # ============================
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

    # Audiências nos próximos 3 dias
    for proc in audiencias:
        try:
            data_aud = datetime.strptime(proc.data_audiencia, "%Y-%m-%d").date()
            if hoje <= data_aud <= hoje + timedelta(days=3):
                alertas.append({
                    "tipo": "audiencia",
                    "texto": f"Audiência em {data_aud.strftime('%d/%m')} — Processo {proc.numero}"
                })
        except:
            pass

    # ============================
    # NOTIFICAÇÕES DO SISTEMA
    # ============================
    notificacoes = []

    # Processos urgentes
    urgentes_lista = Processo.query.filter_by(
        advogado_id=advogado_id,
        prioridade="Urgente"
    ).all()

    for p in urgentes_lista:
        notificacoes.append(f"🔥 Processo {p.numero} está marcado como URGENTE")

    # Processos parados há 7 dias
    sete_dias = datetime.now() - timedelta(days=7)
    parados = Processo.query.filter(
        Processo.advogado_id == advogado_id,
        Processo.data_criacao < sete_dias
    ).all()

    for p in parados:
        notificacoes.append(f"⏳ Processo {p.numero} está sem movimentação há mais de 7 dias")

    # ============================
    # BUSCA GLOBAL
    # ============================
    resultados = None

    if q:
        resultados = {
            "processos": Processo.query.filter(
                Processo.advogado_id == advogado_id,
                Processo.numero.ilike(f"%{q}%")
            ).all(),

            "clientes": Usuario.query.filter(
                Usuario.tipo == "cliente",
                Usuario.nome.ilike(f"%{q}%")
            ).all(),

            "arquivos": ProcessoArquivo.query.filter(
                ProcessoArquivo.nome_original.ilike(f"%{q}%")
            ).all(),

            "prazos": Prazo.query.filter(
                Prazo.titulo.ilike(f"%{q}%")
            ).all()
        }

    # ============================
    # KPIs
    # ============================
    prazos_vencidos = Prazo.query.join(Processo).filter(
        Processo.advogado_id == advogado_id,
        Prazo.data_vencimento < hoje
    ).count()

    audiencias_7_dias = Processo.query.filter(
        Processo.advogado_id == advogado_id,
        Processo.data_audiencia != None,
        Processo.data_audiencia <= (hoje + timedelta(days=7)).strftime("%Y-%m-%d")
    ).count()

    ativos = Processo.query.filter_by(advogado_id=advogado_id, status="Em andamento").count()
    concluidos = Processo.query.filter_by(advogado_id=advogado_id, status="Concluído").count()
    total = Processo.query.filter_by(advogado_id=advogado_id).count()

    taxa = int((concluidos / total) * 100) if total else 0

    # ============================
    # RENDER
    # ============================
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
        google_conectado=google_conectado
    )


# ==========================
# PAINEL ADMIN
# =========================
@app.route("/admin")
@login_required("admin")
def painel_admin():

    # Usuários
    advogados = Usuario.query.filter_by(tipo="advogado").all()
    
    mapa_processos = {}
    for a in advogados:
        mapa_processos[a.id] = Processo.query.filter_by(advogado_id=a.id).count()
    
    
    clientes = Usuario.query.filter_by(tipo="cliente").all()

    # Processos
    processos = Processo.query.all()

    # KPIs
    total_advogados = len(advogados)
    total_clientes = len(clientes)
    total_processos = len(processos)
    em_andamento = Processo.query.filter_by(status="Em andamento").count()
    concluidos = Processo.query.filter_by(status="Concluído").count()

    # Histórico global do sistema
    historico = SistemaLog.query.order_by(SistemaLog.data.desc()).limit(200).all()

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
        mapa_processos=mapa_processos
    )

# ==========================
# ADMIN - CRIAR ADVOGADO
# ==========================
@app.route("/admin/advogado/novo", methods=["POST"])
@login_required("admin")
def admin_novo_advogado():

    nome = request.form["nome"]
    email = request.form["email"]
    senha = generate_password_hash(request.form["senha"])

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

    return redirect(url_for("painel_admin"))


# ==========================
# ADMIN - BLOQUEAR / DESBLOQUEAR
# ==========================
@app.route("/admin/advogado/<int:id>/toggle")
@login_required("admin")
def admin_toggle_advogado(id):

    adv = Usuario.query.get_or_404(id)
    adv.ativo = not adv.ativo

    db.session.commit()

    status = "ativado" if adv.ativo else "bloqueado"
    log_sistema(f"Admin {status} advogado {adv.nome}")

    return redirect(url_for("painel_admin"))

# ==========================
# ADMIN - EDITAR CLIENTE
# ========================
@app.route("/admin/cliente/<int:id>/editar", methods=["GET", "POST"])
@login_required("admin")
def admin_editar_cliente(id):
    cliente = Usuario.query.get_or_404(id)

    if request.method == "POST":
        novo_cpf = re.sub(r"\D", "", request.form["cpf"])

        # Evita CPF duplicado
        existe = Usuario.query.filter(
            Usuario.cpf == novo_cpf,
            Usuario.id != cliente.id
        ).first()

        if existe:
            flash("Esse CPF já está em uso", "danger")
            return redirect(url_for("admin_editar_cliente", id=id))

        cliente.nome = request.form["nome"]
        cliente.cpf = novo_cpf
        cliente.data_nascimento = request.form["data_nascimento"]

        db.session.commit()
        flash("Cliente atualizado", "success")
        return redirect(url_for("painel_admin"))

    return render_template("cliente_editar.html", cliente=cliente)

# ==========================
# ADMIN - EXCLUIR CLIENTE
# ==========================
@app.route("/admin/cliente/<int:id>/excluir", methods=["POST"])
@login_required("admin")
def admin_excluir_cliente(id):

    cliente = Usuario.query.get_or_404(id)

    Processo.query.filter_by(cliente_id=id).delete()
    db.session.delete(cliente)
    db.session.commit()

    log_sistema(f"Admin excluiu cliente {cliente.nome}")

    return redirect(url_for("painel_admin"))


# ==========================
# ADMIN - EXCLUIR PROCESSO
# ==========================
@app.route("/admin/processo/<int:id>/excluir", methods=["POST"])
@login_required("admin")
def admin_excluir_processo(id):

    processo = Processo.query.get_or_404(id)

    ProcessoArquivo.query.filter_by(processo_id=id).delete()
    ProcessoTag.query.filter_by(processo_id=id).delete()
    ProcessoHistorico.query.filter_by(processo_id=id).delete()

    db.session.delete(processo)
    db.session.commit()

    log_sistema(f"Admin excluiu processo {processo.numero}")

    return redirect(url_for("painel_admin"))

# ==========================
# PAINEL Cliente
# =========================
@app.route("/painel/cliente")
@login_required("cliente")
def painel_cliente():

    cliente_id = session["usuario_id"]   # 👈 PRIMEIRO define

    # =========================
    # PROCESSOS DO CLIENTE
    # =========================
    processos = Processo.query.filter_by(cliente_id=cliente_id).all()

    total = len(processos)
    em_andamento = len([p for p in processos if p.status == "Em andamento"])
    concluidos = len([p for p in processos if p.status == "Concluído"])

    # =========================
    # PRÓXIMA AUDIÊNCIA
    # =========================
    proxima = None
    audiencias = [p for p in processos if p.data_audiencia]

    if audiencias:
        audiencias.sort(key=lambda x: x.data_audiencia)
        proxima = audiencias[0]

    # =========================
    # NOTIFICAÇÕES DO CLIENTE
    # =========================
    notificacoes = NotificacaoCliente.query.filter_by(
        cliente_id=cliente_id,
        lida=False
    ).order_by(NotificacaoCliente.data.desc()).all()

    return render_template(
        "painel_cliente_dashboard.html",
        processos=processos,
        total=total,
        em_andamento=em_andamento,
        concluidos=concluidos,
        proxima=proxima,
        notificacoes=notificacoes
    )

# ==========================
# PROCESSOS
# ==========================
@app.route('/advogado/processos')
@login_required('advogado')
def processos_advogado():
    advogado_id = session['usuario_id']
    q = request.args.get("q")

    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')
    prioridade = request.args.get('prioridade')
    cliente = request.args.get('cliente')
    busca = request.args.get('busca')

    query = Processo.query

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

    clientes = Usuario.query.filter_by(tipo='cliente').all()

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
        db.session.commit()   # 👈 O processo precisa existir no banco primeiro

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
                data_vencimento=datetime.strptime(prazo_data, "%Y-%m-%d").date(),
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


        # Histórico
        db.session.add(ProcessoHistorico(
            acao='Processo criado',
            processo_id=processo.id
        ))

        log_sistema(f"Criou processo {processo.numero}")

        
        # 📅 Dados da audiência
        data_audiencia = request.form.get('data_audiencia')
        hora_audiencia = request.form.get('hora_audiencia')

        if data_audiencia and hora_audiencia:
            try:
                event_id = criar_evento_google(
                    titulo=f"Audiência - Processo {processo.numero}",
                    descricao=processo.descricao or "",
                    data=data_audiencia,
                    hora=hora_audiencia
                )
            except:
                event_id= None  

            processo.data_audiencia = data_audiencia
            processo.hora_audiencia = hora_audiencia
            processo.google_event_id = event_id

        # TAGS
        tags = request.form.get('tags')
        if tags:
            for tag in tags.split(','):
                db.session.add(ProcessoTag(
                    nome=tag.strip(),
                    processo_id=processo.id
                ))

        # ARQUIVOS
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

    clientes = Usuario.query.filter_by(tipo='cliente').all()
    return render_template('processo_novo.html', clientes=clientes)


# ==========================
# DETALHE DO PROCESSO
# ==========================

from datetime import date, timedelta

@app.route("/processo/<int:id>", methods=["GET", "POST"], endpoint="detalhe_processo")
@login_required()
def detalhe_processo(id):
    processo = Processo.query.get_or_404(id)
    
   # 🔐 Regra de permissão
    # Todos podem VER
    # Apenas dono ou admin podem ALTERAR
    pode_editar = pode_editar_processo(processo)

    if request.method == "POST":
        if not pode_editar:
            flash("Você não tem permissão para alterar este processo.", "danger")
            return redirect(url_for("detalhe_processo", id=id))

        # ===============================
        # ATUALIZAR STATUS / PRIORIDADE / OBS
        # ===============================
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

        
        # ===============================
        # ATUALIZAR AUDIÊNCIA
        # ===============================
        data_aud = request.form.get("data_audiencia")
        hora_aud = request.form.get("hora_audiencia")

        if data_aud and hora_aud:
            db.session.add(NotificacaoCliente(
                cliente_id=processo.cliente_id,
                mensagem=f"Audiência marcada para {data_aud} às {hora_aud} no processo {processo.numero}"
            ))
            # Se já existia evento, apagar no Google
            if processo.google_event_id:
                service = get_calendar_service()
                if service:
                    try:
                        service.events().delete(
                            calendarId="primary",
                            eventId=processo.google_event_id
                        ).execute()
                    except:
                        pass

            # Criar novo evento
            event_id = criar_evento_google(
                titulo=f"Audiência - Processo {processo.numero}",
                descricao=processo.descricao or "",
                data=data_aud,
                hora=hora_aud
            )

            processo.data_audiencia = data_aud
            processo.hora_audiencia = hora_aud
            processo.google_event_id = event_id

            db.session.add(ProcessoHistorico(
                processo_id=id,
                acao=f"Audiência definida para {data_aud} às {hora_aud}"
            ))

            


        # ===============================
        # UPLOAD DE NOVOS PDFs
        # ===============================
        if "arquivos" in request.files:
            for arquivo in request.files.getlist("arquivos"):
                if arquivo and allowed_file(arquivo.filename):
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

    # ===============================
    # CARREGAR DADOS (GET)
    # ===============================
    tags = ProcessoTag.query.filter_by(processo_id=id).all()
    arquivos = ProcessoArquivo.query.filter_by(processo_id=id).all()
    historico = ProcessoHistorico.query.filter_by(processo_id=id).order_by(ProcessoHistorico.data.desc()).all()
    prazos = Prazo.query.filter_by(processo_id=id).order_by(Prazo.data_vencimento.asc()).all()

    hoje = date.today()
    amanha = hoje + timedelta(days=1)

    alertas = []
    for p in prazos:
        if p.data_vencimento == amanha:
            alertas.append(f"O prazo '{p.titulo}' vence amanhã!")
        elif p.data_vencimento < hoje:
            alertas.append(f"O prazo '{p.titulo}' está vencido!")

    return render_template(
        "processo_detalhe.html",
        processo=processo,
        tags=tags,
        arquivos=arquivos,
        historico=historico,
        prazos=prazos,
        hoje=hoje,
        alertas=alertas
    )

# ==========================
# EXCLUIR PROCESSO
# ==========================
@app.route('/advogado/processos/<int:id>/excluir', methods=['POST'])
@login_required('advogado')
def excluir_processo(id):
    processo = Processo.query.get_or_404(id)

    # 🔐 Somente o advogado dono pode apagar
    if processo.advogado_id != session["usuario_id"]:
        flash("Você não tem permissão para excluir este processo", "danger")
        return redirect(url_for("processos_advogado"))

    # Google Calendar
    if processo.google_event_id:
        service = get_calendar_service()
        if service:
            try:
                service.events().delete(
                    calendarId='primary',
                    eventId=processo.google_event_id
                ).execute()
            except:
                pass

    # Apagar PDFs físicos
    arquivos = ProcessoArquivo.query.filter_by(processo_id=id).all()
    for arq in arquivos:
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], arq.nome_arquivo)
        if os.path.exists(caminho):
            os.remove(caminho)

    # Banco
    ProcessoArquivo.query.filter_by(processo_id=id).delete()
    ProcessoTag.query.filter_by(processo_id=id).delete()
    ProcessoHistorico.query.filter_by(processo_id=id).delete()

    log_sistema(f"Excluiu o processo {processo.numero}")

    db.session.delete(processo)
    db.session.commit()

    flash("Processo excluído", "success")
    return redirect(url_for("processos_advogado"))

# ==========================
# DOWNLOAD PDF
# ==========================
@app.route("/arquivo/<int:id>/download")
@login_required()
def baixar_pdf(id):

    arquivo = ProcessoArquivo.query.get_or_404(id)
    processo = Processo.query.get(arquivo.processo_id)

    # Admin pode tudo
    if session["usuario_tipo"] == "admin":
        pass

    # Advogado só se for dono
    elif session["usuario_tipo"] == "advogado":
        if processo.advogado_id != session["usuario_id"]:
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

    # apagar arquivo físico
    caminho = os.path.join(app.config["UPLOAD_FOLDER"], arquivo.nome_arquivo)
    if os.path.exists(caminho):
        os.remove(caminho)

    # histórico
    db.session.add(ProcessoHistorico(
        processo_id=arquivo.processo_id,
        acao=f"Arquivo removido: {arquivo.nome_original}"
    ))

    log_sistema(f"Removeu arquivo {arquivo.nome_original}")


    # apagar do banco
    db.session.delete(arquivo)
    db.session.commit()

    return redirect(url_for("detalhe_processo", id=arquivo.processo_id))

# ==========================
# CRIAR USUÁRIOS TESTE
# ==========================
@app.route('/seed')
def seed():
    db.drop_all()
    db.create_all()

    # Admin
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
    db.session.commit()   # 🔥 AQUI os IDs são criados

    advogados = [adv1, adv2, adv3]

    clientes = []

    for i in range(1, 11):
        if i <= 4:
            advogado = adv1  # João
        elif i <= 7:
            advogado = adv2  # Maria
        else:
            advogado = adv3  # Pedro

        cliente = Usuario(
            nome=f"Cliente {i}",
            cpf=f"10000000{i}",
            data_nascimento="1990-01-01",
            tipo="cliente",
            advogado_id=advogado.id
        )
        clientes.append(cliente)


    db.session.add_all(clientes)
    db.session.commit()

    # ===============================
    # PROCESSOS
    # ===============================
    advogados = [adv1, adv2, adv3]

    processos = []

    for i, cliente in enumerate(clientes):
        advogado = advogados[i % 3]

        processo = Processo(
            numero=f"2025.000{i+1}",
            status="Em andamento" if i < 7 else "Concluído",
            prioridade="Urgente" if i in [1,4,7] else "Normal",
            cliente_id=cliente.id,
            advogado_id=advogado.id,
            criado_por=advogado.id,
            descricao="Processo de teste"
        )

        # Audiência para 4 clientes
        if i < 4:
            processo.data_audiencia = (datetime.now() + timedelta(days=i+1)).strftime("%Y-%m-%d")
            processo.hora_audiencia = "10:00"

        db.session.add(processo)
        db.session.commit()
        processos.append(processo)

        db.session.add(ProcessoHistorico(
            processo_id=processo.id,
            usuario_id=advogado.id,
            acao="Processo criado"
        ))

    # ===============================
    # PRAZOS
    # ===============================
    for i, p in enumerate(processos):
        if i % 2 == 0:
            prazo = Prazo(
                titulo=f"Prazo do processo {p.numero}",
                descricao="Prazo legal",
                data_vencimento=(datetime.now() + timedelta(days=i+2)).date(),
                processo_id=p.id
            )
            db.session.add(prazo)

    db.session.commit()

    return "🔥 Sistema populado com sucesso! Agora teste como Admin, Advogado e Cliente."

# ==========================
# START
# ==========================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
