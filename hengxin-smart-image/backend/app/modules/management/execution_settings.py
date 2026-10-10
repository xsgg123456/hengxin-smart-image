from fastapi import APIRouter
from app.contracts.execution_settings import ExecutionSettings
from app.core.config import get_settings
from app.modules.api_image_edits.config import get_api_settings, PARAMETERS
from app.modules.api_image_edits.scheduling import TASK_CONCURRENCY, IMAGES_PER_TASK
from app.modules.api_image_edits.execution_policy import CLI_MODEL, CLI_REASONING_EFFORT, CLI_USES_SKILLS
from .settings import values
from .settings_router import Admin, Database
from app.retention.state import CACHE_AGE, HISTORY_AGE

router = APIRouter(tags=['management'])


@router.get('/management/execution-settings', response_model=ExecutionSettings)
def execution_settings(user: Admin, session: Database):
    api, env, config = get_api_settings(), get_settings(), values(session)
    return dict(api=dict(enabled=api.enabled, taskConcurrency=TASK_CONCURRENCY,
        imagesPerBatch=IMAGES_PER_TASK, requestTimeoutSeconds=api.request_timeout_seconds,
        downloadTimeoutSeconds=api.download_timeout_seconds, leaseSeconds=api.lease_seconds,
        model=PARAMETERS['model'], quality=PARAMETERS['quality'], resolution=PARAMETERS['resolution'],
        imagesPerRequest=PARAMETERS['n'], sizePolicy='跟随原图宽高'), cli=dict(enabled=env.enable_codex_executor,
        concurrency=config['concurrency'], capacity=env.generation_concurrency,
        timeoutSeconds=config['timeoutSeconds'], timeoutCapacity=env.codex_timeout_seconds,
        model=CLI_MODEL, reasoningEffort=CLI_REASONING_EFFORT, usesSkills=CLI_USES_SKILLS),
        maxUploadBytes=config['maxUploadBytes'], retention=dict(enabled=env.cli_retention_enabled,
            cacheIdleDays=CACHE_AGE.days, historyIdleDays=HISTORY_AGE.days))
