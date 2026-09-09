from celery import Celery

from app.core.config import get_settings

celery_app = Celery("hengxin", broker=get_settings().redis_url,
                    include=["app.worker.tasks"])
celery_app.conf.update(
    task_acks_late=True, task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, task_ignore_result=True,
    task_serializer="json", accept_content=["json"],
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=3,
    broker_transport_options={"visibility_timeout": 60,
                              "socket_connect_timeout": 3, "socket_timeout": 3},
)
