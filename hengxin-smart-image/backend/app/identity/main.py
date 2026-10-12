"""Neutral identity service: no business database, storage or queue dependencies."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from redis import Redis
from redis.exceptions import RedisError
from app.errors import error_response, register_errors
from app.identity.config import IdentitySettings
from app.identity.router import router
from app.identity.store import IdentityStore


def create_app(settings=None, redis_client=None):
    @asynccontextmanager
    async def lifespan(application):
        config = settings or IdentitySettings()
        client = redis_client or Redis.from_url(config.redis_url, decode_responses=True,
                                                socket_timeout=3, socket_connect_timeout=3)
        application.state.settings = config
        application.state.store = IdentityStore(client, config.session_ttl_seconds)
        try:
            client.ping()
            yield
        finally:
            if redis_client is None:
                client.close()

    application = FastAPI(title='恒鑫统一身份服务', lifespan=lifespan)
    register_errors(application)

    @application.exception_handler(RedisError)
    async def redis_error(request, error):
        return error_response(request, 503, 'IDENTITY_UNAVAILABLE', '统一身份服务暂不可用')

    @application.middleware('http')
    async def no_cache(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    application.include_router(router)
    return application


app = create_app()
