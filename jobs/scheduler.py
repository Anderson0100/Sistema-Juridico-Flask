from apscheduler.schedulers.background import BackgroundScheduler
from services.monitor import atualizar_processos

_scheduler = None


def iniciar_scheduler(app):
    global _scheduler

    if _scheduler and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler()

    def job():
        with app.app_context():
            atualizar_processos()

    scheduler.add_job(job, trigger="interval", hours=1)
    scheduler.start()
    _scheduler = scheduler
    return scheduler
