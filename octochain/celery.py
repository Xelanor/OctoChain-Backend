import os

from celery import Celery
from celery.signals import worker_ready
import celery.signals


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "octochain.settings")
app = Celery("octochain")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@celery.signals.setup_logging.connect
def on_celery_setup_logging(**kwargs):
    pass


@worker_ready.connect
def at_start(sender, **k):
    with sender.app.connection() as conn:
        # sender.app.send_task("hedge_bot.tasks.run_hedge_bot")
        # sender.app.send_task("hedge_bot.tasks.run_hedge_open_bot")
        pass
