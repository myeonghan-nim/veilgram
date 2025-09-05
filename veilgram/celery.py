import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "veilgram.settings")

app = Celery("veilgram")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def health(self):
    return "ok"
