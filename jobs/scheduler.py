from apscheduler.schedulers.background import BackgroundScheduler
from services.monitor import atualizar_processos


def iniciar_scheduler(app):
    scheduler = BackgroundScheduler()

    def job():
        with app.app_context():
            atualizar_processos()

    scheduler.add_job(job, trigger="interval", hours=1)
    scheduler.start()