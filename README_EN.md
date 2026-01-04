## ⚖️ Legal Management System – Flask + MySQL

A complete web system for law firm management, developed with Python (Flask) and MySQL, featuring authentication, process control, clients, deadlines, document uploads and Google Calendar integration.

This project was built focusing on real backend architecture, security and professional development practices.

## 🚀 Features

✔️ User authentication (Admin, Lawyer, Client)
✔️ Client management
✔️ Legal case (process) management
✔️ Deadlines and hearings
✔️ File upload (PDF documents)
✔️ Google Calendar integration
✔️ Role-based access control
✔️ Lawyer and client dashboards
✔️ Secure sessions and password hashing

## 🛠️ Technologies

Python 3

Flask

MySQL

SQLAlchemy

HTML, CSS, JavaScript

Google Calendar API

dotenv (.env)

Werkzeug (password hashing)

## 📂 Project Structure
Sistema-Juridico-Flask/
│
├── app.py
├── google_calendar.py
├── requirements.txt
├── .env (ignored)
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

## 🔐 Environment Variables

Create a .env file in the project root:

SECRET_KEY=your_secret_key
DATABASE_URL=mysql+pymysql://user:password@localhost/database_name
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret


The .env file is ignored by Git for security reasons.

## 🧪 How to run locally
1️⃣ Clone the repository
git clone https://github.com/Anderson0100/Sistema-Juridico-Flask.git
cd Sistema-Juridico-Flask

2️⃣ Create virtual environment
python -m venv venv
venv\Scripts\activate

3️⃣ Install dependencies
pip install -r requirements.txt

4️⃣ Configure .env

Create your .env file with your credentials.

5️⃣ Run the server
python app.py


Access:

http://127.0.0.1:5000

## 🎯 Project Goal

This project was built as a professional portfolio, demonstrating:

Real backend development

API integration

Authentication & security

MVC architecture

Relational database

Production-ready structure

## 👨‍💻 Author

Anderson Junior
GitHub: https://github.com/Anderson0100