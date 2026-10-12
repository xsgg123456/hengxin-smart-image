"""Separate broker context and queue; never imports the domestic worker."""
from celery import Celery
from app.core.config import get_settings
from app.overseas.db import require_overseas_context, session_factory
from .runner import run

require_overseas_context()
settings = get_settings()
celery_app = Celery('hengxin-overseas', broker=settings.redis_url)
celery_app.conf.update(
    task_default_queue='overseas.cli', task_acks_late=True,
    task_reject_on_worker_lost=True, worker_prefetch_multiplier=1,
    task_ignore_result=True, task_serializer='json', accept_content=['json'],
    broker_connection_retry_on_startup=True, broker_connection_timeout=3,
    broker_transport_options={'visibility_timeout': settings.queue_visibility_seconds,
                              'socket_connect_timeout': 3, 'socket_timeout': 3},
)


@celery_app.task(name='hengxin.overseas.job')
def execute_job(job_id):
    run(session_factory(), job_id)
