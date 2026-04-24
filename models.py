from services.db import db
from datetime import datetime, timedelta

# ==========================
# FUNÇÃO DE DATA BR
# ==========================
def agora_br():
    return datetime.utcnow() - timedelta(hours=3)


# ==========================
# USUÁRIO
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
    telefone = db.Column(db.String(20))

    google_access_token = db.Column(db.Text)
    google_refresh_token = db.Column(db.Text)
    google_token_expiry = db.Column(db.DateTime)
    google_connected = db.Column(db.Boolean, default=False)

    advogado_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    advogado = db.relationship("Usuario", foreign_keys=[advogado_id])

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

# ==========================
# MENSAGEM ZAP
# ==========================
class Mensagem(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    destinatario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))

    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"))

    texto = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.utcnow)

    origem = db.Column(db.String(20))  # cliente ou advogado

    usuario = db.relationship("Usuario", foreign_keys=[usuario_id])
    destinatario = db.relationship("Usuario", foreign_keys=[destinatario_id])

    processo = db.relationship("Processo")

# ==========================
# ATENDIMENTO / AGENDAMENTO INTERNO
# ==========================
class AtendimentoInterno(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    cliente_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)
    advogado_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)
    criado_por = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)

    nome_cliente = db.Column(db.String(150), nullable=False)
    telefone = db.Column(db.String(20))
    assunto = db.Column(db.String(200), nullable=False)
    observacao = db.Column(db.Text)

    tipo = db.Column(db.String(30), default="atendimento")  # atendimento, audiencia, lembrete, retorno

    data_movimentacao = db.Column(db.DateTime)
    ultima_verificacao = db.Column(db.DateTime)    # HH:MM

    status = db.Column(db.String(30), default="Pendente")
    criado_em = db.Column(db.DateTime, default=agora_br)

    cliente = db.relationship("Usuario", foreign_keys=[cliente_id])
    advogado = db.relationship("Usuario", foreign_keys=[advogado_id])
    criador = db.relationship("Usuario", foreign_keys=[criado_por])

# ==========================
# AGENDAMENTO DE ATENDIMENTO PRESENCIAL
# ==========================
class AgendamentoAtendimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    cliente_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)
    advogado_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    criado_por = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)

    nome_cliente = db.Column(db.String(150), nullable=False)
    telefone = db.Column(db.String(20))
    assunto = db.Column(db.String(200))
    observacao = db.Column(db.Text)

    data_agendada = db.Column(db.String(10), nullable=False)   # YYYY-MM-DD
    hora_agendada = db.Column(db.String(5), nullable=False)    # HH:MM

    status = db.Column(db.String(30), default="Marcado")  # Marcado, Confirmado, Concluído, Cancelado
    criado_em = db.Column(db.DateTime, default=agora_br)

    cliente = db.relationship("Usuario", foreign_keys=[cliente_id])
    advogado = db.relationship("Usuario", foreign_keys=[advogado_id])
    criador = db.relationship("Usuario", foreign_keys=[criado_por])


# ==========================
# RECADOS / AVISOS INTERNOS
# ==========================
class RecadoInterno(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    cliente_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)
    advogado_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)
    criado_por = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)

    nome_cliente = db.Column(db.String(150), nullable=False)
    telefone = db.Column(db.String(20))
    canal = db.Column(db.String(30), default="ligacao")  # ligacao, whatsapp, interno, presencial
    assunto = db.Column(db.String(200), nullable=False)
    recado = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(30), default="Pendente")  # Pendente, Lido, Resolvido
    criado_em = db.Column(db.DateTime, default=agora_br)

    cliente = db.relationship("Usuario", foreign_keys=[cliente_id])
    advogado = db.relationship("Usuario", foreign_keys=[advogado_id])
    criador = db.relationship("Usuario", foreign_keys=[criado_por])

# ==========================
# PROCESSO
# ==========================
class Processo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), nullable=False, unique=True, index=True)
    status = db.Column(db.String(20), default='Em andamento')
    prioridade = db.Column(db.String(20), default='Normal')
    descricao = db.Column(db.Text)
    data_criacao = db.Column(db.DateTime, default=agora_br)

    data_audiencia = db.Column(db.String(10))
    hora_audiencia = db.Column(db.String(5))
    google_event_id = db.Column(db.String(255))

    advogado_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    criado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

    advogado = db.relationship("Usuario", foreign_keys=[advogado_id])
    criador = db.relationship("Usuario", foreign_keys=[criado_por])
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id])

    prazos = db.relationship('Prazo', backref='processo', lazy=True)
    observacoes = db.relationship("Observacao", backref="processo_rel", lazy=True)

    ultima_movimentacao = db.Column(db.String(300))
    data_movimentacao = db.Column(db.DateTime)
    tribunal = db.Column(db.String(20))  # TRF1, TRF5, TRT1
    status_monitoramento = db.Column(db.String(20), default="ativo")
    ultima_verificacao = db.Column(db.DateTime)

# ==========================
# MOVIMENTAÇÃO PROCESSUAL
# ==========================
class MovimentacaoProcessual(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"))
    data = db.Column(db.DateTime)
    descricao = db.Column(db.Text)
    tribunal = db.Column(db.String(20))

    processo = db.relationship("Processo", backref="movimentacoes")


# ==========================
# ARQUIVOS
# ==========================
class ProcessoArquivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_original = db.Column(db.String(200))
    nome_arquivo = db.Column(db.String(200))
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))


class ProcessoTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50))
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))


# ==========================
# HISTÓRICO PROCESSO
# ==========================
class ProcessoHistorico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    acao = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=agora_br)
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

    usuario = db.relationship("Usuario")


# ==========================
# LOG SISTEMA
# ==========================
class SistemaLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer)
    usuario_nome = db.Column(db.String(150))
    acao = db.Column(db.String(300))
    data = db.Column(db.DateTime, default=agora_br)


# ==========================
# NOTIFICAÇÃO CLIENTE
# ==========================
class NotificacaoCliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    mensagem = db.Column(db.String(300))
    lida = db.Column(db.Boolean, default=False)
    data = db.Column(db.DateTime, default=agora_br)


# ==========================
# PRAZO
# ==========================
class Prazo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150))
    descricao = db.Column(db.String(200), nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Aberto')
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))


# ==========================
# OBSERVAÇÃO
# ==========================
class Observacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.Text, nullable=False)
    data = db.Column(db.DateTime, default=agora_br)

    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'), nullable=False)
    advogado_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    advogado = db.relationship("Usuario")
    processo = db.relationship("Processo")