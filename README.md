# ⚖️ Sistema Jurídico Completo – Flask + MySQL + WhatsApp

Sistema web completo para gestão de escritórios de advocacia, desenvolvido com **Python (Flask)**, banco de dados **MySQL** e integração com **WhatsApp, Google Calendar e APIs jurídicas**.

Projeto com arquitetura real de backend, pronto para uso em ambiente profissional.

---

## 🧠 Visão Geral

O sistema permite que escritórios de advocacia gerenciem:

- Clientes
- Processos
- Prazos
- Audiências
- Atendimento via WhatsApp
- Comunicação interna

Tudo em um único ambiente integrado.

---

## 🚀 Principais Funcionalidades

### 👥 Gestão de Usuários
- Login com autenticação segura
- Perfis: **Admin, Advogado e Cliente**
- Controle de permissões por tipo de usuário

---

### ⚖️ Gestão Jurídica
- Cadastro de processos
- Acompanhamento de andamento
- Controle de prazos
- Registro de movimentações
- Upload de documentos (PDF)

---

### 📅 Agenda e Organização
- Integração com **Google Calendar**
- Controle de audiências e compromissos
- Visualização centralizada de tarefas

---

### 🤖 Atendimento Inteligente (WhatsApp)
- Bot automático para atendimento inicial
- Menu interativo para clientes
- Consulta de processos via mensagem
- Encaminhamento para atendimento humano
- Sistema de fila de atendimento

---

### 📊 Dashboard
- Painel do advogado com visão geral
- Painel do cliente para acompanhamento
- Indicadores e resumo do sistema

---

## 🔗 Integrações

- 📅 Google Calendar API
- 💬 WhatsApp API (via Docker)
- ⚖️ DataJud (consulta de processos)
- 🤖 OpenAI (respostas inteligentes)

---

## 🛠️ Tecnologias Utilizadas

- Python 3
- Flask
- MySQL
- SQLAlchemy
- HTML, CSS e JavaScript
- Docker
- Postman (testes de API)
- dotenv (.env)
- Werkzeug (segurança de senhas)

---

## 📂 Estrutura do Projeto


Sistema-Juridico-Flask/
│
├── app.py
├── core/
├── routes/
├── services/
├── utils/
│
├── templates/
├── static/
├── uploads/
│
├── whatsapp/
├── whatsapp-api/


---

## 🔐 Segurança

- Senhas criptografadas (hash)
- Sessões protegidas
- Variáveis sensíveis via `.env`
- Controle de acesso por perfil

---

## ⚙️ Como Executar

### 1️⃣ Clonar o projeto

git clone https://github.com/Anderson0100/Sistema-Juridico-Flask.git

cd Sistema-Juridico-Flask


### 2️⃣ Criar ambiente virtual

python -m venv venv
venv\Scripts\activate


### 3️⃣ Instalar dependências

pip install -r requirements.txt


### 4️⃣ Configurar variáveis
Crie um arquivo `.env`:


SECRET_KEY=
DATABASE_URL=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
OPENAI_API_KEY=


### 5️⃣ Rodar o sistema

python app.py


Acesse:

http://127.0.0.1:5000


---

## 📲 WhatsApp (Docker)


cd whatsapp-api
docker-compose up -d


Webhook:

/webhook/whatsapp


---

## 🎯 Objetivo do Projeto

Este sistema foi desenvolvido para:

- Demonstrar conhecimento em backend real
- Trabalhar com APIs externas
- Construir um sistema completo do zero
- Aplicar boas práticas de segurança e arquitetura

---

## 👨‍💻 Autor

**Anderson Junior**  
GitHub: https://github.com/Anderson0100