## ⚖️ Sistema Jurídico – Flask + MySQL

Sistema web completo para gestão de escritórios de advocacia, desenvolvido em Python (Flask) com banco de dados MySQL, autenticação de usuários, controle de processos, clientes e integração com Google Calendar.

Projeto desenvolvido com foco em boas práticas, segurança, organização de código e arquitetura backend real.

## 🚀 Funcionalidades

✔️ Autenticação de usuários (Admin, Advogado e Cliente)
✔️ Controle de clientes
✔️ Controle de processos
✔️ Cadastro e acompanhamento de prazos
✔️ Audiências e agenda
✔️ Upload de documentos (PDFs)
✔️ Integração com Google Calendar
✔️ Sistema de permissões por tipo de usuário
✔️ Dashboard para advogado e cliente
✔️ Segurança de sessão e autenticação

## 🛠️ Tecnologias Utilizadas

Python 3

Flask

MySQL

SQLAlchemy

HTML, CSS e JavaScript

Google Calendar API

dotenv (.env)

Werkzeug (hash de senhas)

📂 Estrutura do Projeto
Sistema-Juridico-Flask/
│
├── app.py
├── google_calendar.py
├── requirements.txt
├── .env (não versionado)
├── templates/
│   ├── login.html
│   ├── painel_advogado.html
│   ├── painel_cliente.html
│   ├── processos.html
│   └── ...
├── static/
│   ├── css/
│   └── js/
└── uploads/

## 🔐 Variáveis de Ambiente

Crie um arquivo .env na raiz do projeto:

SECRET_KEY=suachave
DATABASE_URL=mysql+pymysql://usuario:senha@localhost/nome_do_banco
GOOGLE_CLIENT_ID=seu_client_id
GOOGLE_CLIENT_SECRET=seu_client_secret


O arquivo .env é ignorado pelo Git por segurança.

## 🧪 Como rodar o projeto localmente
1️⃣ Clone o repositório
git clone https://github.com/Anderson0100/Sistema-Juridico-Flask.git
cd Sistema-Juridico-Flask

2️⃣ Crie o ambiente virtual
python -m venv venv
venv\Scripts\activate   # Windows

3️⃣ Instale as dependências
pip install -r requirements.txt

4️⃣ Configure o .env

Crie o arquivo .env conforme explicado acima.

5️⃣ Rode o servidor
python app.py


Acesse:

http://127.0.0.1:5000

## 🎯 Objetivo do Projeto

Este sistema foi desenvolvido como parte de um portfólio profissional, demonstrando:

Backend real em Flask

Integração com APIs externas

Segurança de autenticação

Estrutura MVC

Banco de dados relacional

Projeto pronto para produção

## 👨‍💻 Autor

Anderson Junior
📎 GitHub: https://github.com/Anderson0100