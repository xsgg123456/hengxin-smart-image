"""Redis-only identity sessions and atomically consumed, business-bound grants."""
from dataclasses import asdict
from datetime import datetime, timedelta
import json
from fastapi import HTTPException
from app.identity.tokens import hash_token, new_token, utcnow, is_expired
from app.identity.schemas import Member
from pydantic import ValidationError

PREFIX = 'hx:identity:'


class IdentityStore:
    def __init__(self, redis_client, ttl_seconds):
        self.redis = redis_client
        self.ttl = ttl_seconds

    def create(self, member):
        token, sid = new_token(), new_token()
        try:
            profile = Member.model_validate(asdict(member)).model_dump()
        except ValidationError as error:
            raise HTTPException(503, '钉钉成员信息不符合接口约定') from error
        record = {'member': profile, 'identity_session_id': sid,
                  'expires_at': (utcnow() + timedelta(seconds=self.ttl)).isoformat(),
                  'token_hash': hash_token(token)}
        with self.redis.pipeline(transaction=True) as pipe:
            pipe.set(PREFIX + 'session:' + sid, json.dumps(record), ex=self.ttl)
            pipe.set(PREFIX + 'token:' + hash_token(token), sid, ex=self.ttl)
            pipe.execute()
        return token

    def by_id(self, sid):
        raw = self.redis.get(PREFIX + 'session:' + sid)
        record = json.loads(raw) if raw else None
        if record and not is_expired(datetime.fromisoformat(record['expires_at'])):
            return record
        return None

    def resolve(self, token):
        sid = self.redis.get(PREFIX + 'token:' + hash_token(token or ''))
        if isinstance(sid, bytes):
            sid = sid.decode()
        record = self.by_id(sid) if sid else None
        if not record:
            raise HTTPException(401, '统一身份未登录或已失效')
        return record

    def revoke(self, token):
        token_key = PREFIX + 'token:' + hash_token(token or '')
        sid = self.redis.getdel(token_key)
        if isinstance(sid, bytes):
            sid = sid.decode()
        if sid:
            self.redis.delete(PREFIX + 'session:' + sid)

    def ticket(self, record, business):
        ticket = new_token()
        self.redis.set(PREFIX + 'ticket:' + business + ':' + hash_token(ticket),
                       record['identity_session_id'], ex=60)
        return ticket

    def redeem(self, ticket, business):
        sid = self.redis.getdel(PREFIX + 'ticket:' + business + ':' + hash_token(ticket))
        if isinstance(sid, bytes):
            sid = sid.decode()
        record = self.by_id(sid) if sid else None
        if not record:
            raise HTTPException(401, '身份凭据无效或已过期')
        return {key: record[key] for key in ('member', 'identity_session_id', 'expires_at')}

    def state(self):
        state = new_token()
        self.redis.set(PREFIX + 'state:' + hash_token(state), '1', ex=600)
        return state

    def consume_state(self, state):
        return bool(self.redis.getdel(PREFIX + 'state:' + hash_token(state)))
