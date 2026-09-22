import logging

from celery import Celery

from .config import get_api_settings

celery_app = Celery('api_image_edits', broker=get_api_settings().broker_url)
celery_app.conf.update(
    task_default_queue='api_image_edits', task_serializer='json', accept_content=['json'],
    task_ignore_result=True, task_acks_late=True, task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, broker_connection_retry_on_startup=True,
    broker_transport_options={'visibility_timeout': 900},
)


@celery_app.task(name='api_image_edits.execute')
def execute():
    try:
        from app.db.session import session_factory
        from app.storage.minio_store import get_store
        from .execution import execute_batch
        execute_batch(session_factory(), get_store())
    except Exception:
        # SQL/transport exceptions may embed private receipt URLs or image bytes.
        # Leave the durable lease intact: outbox recovery must decide whether the
        # operation is uncertain or collection-only, never blindly regenerate.
        logging.getLogger(__name__).error('API_IMAGE_EXECUTION_FAILED: 等待持久状态恢复')
