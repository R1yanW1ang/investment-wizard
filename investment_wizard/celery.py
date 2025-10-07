import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investment_wizard.settings')

app = Celery('investment_wizard')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule (5-minute scraping frequency)
# Configured here to avoid circular import issues
app.conf.beat_schedule = {
    'scrape-every-5-minutes': {
        'task': 'src.tasks.scrape_articles_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'cleanup-daily': {
        'task': 'src.tasks.cleanup_old_articles_task',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
