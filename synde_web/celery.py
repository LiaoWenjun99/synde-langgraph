"""Celery configuration for synde_web."""

import os
from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'synde_web.settings')

app = Celery('synde_web')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Task routing
app.conf.task_routes = {
    # GPU tasks (defined in synde-minimal, called from synde-langgraph)
    'home.tasks.run_esmfold_job': {'queue': 'gpu'},
    'home.tasks.run_clean_ec_job': {'queue': 'gpu'},
    'home.tasks.run_deepenzyme_kcat_job': {'queue': 'gpu'},
    'home.tasks.run_temperture_job': {'queue': 'gpu'},
    'home.tasks.run_flan_extractor': {'queue': 'gpu'},
    'home.tasks.run_fpocket_job': {'queue': 'gpu'},
    'home.tasks.run_progen2_job': {'queue': 'gpu'},
    'home.tasks.run_zymctrl_job': {'queue': 'gpu'},

    # Workflow task (CPU queue)
    'synde_web.tasks.run_workflow': {'queue': 'default'},
    'synde_web.tasks.cleanup_expired_checkpoints': {'queue': 'default'},
}

# Beat schedule for periodic tasks
app.conf.beat_schedule = {
    'cleanup-expired-checkpoints': {
        'task': 'synde_web.tasks.cleanup_expired_checkpoints',
        'schedule': 3600.0,  # Every hour
        'args': (7,),  # Delete checkpoints older than 7 days
    },
}


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f'Request: {self.request!r}')
