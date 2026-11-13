from fastapi.responses import StreamingResponse


class OwnedStreamResponse(StreamingResponse):
    """Own the HTTP connection even if the client disconnects before iteration starts."""
    def __init__(self, stream, **kwargs):
        self.stream = stream
        chunks = (stream.stream(64 * 1024) if callable(getattr(stream, 'stream', None))
                  else iter(lambda: stream.read(64 * 1024), b''))
        super().__init__(chunks, **kwargs)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                self.stream.close()
            finally:
                release = getattr(self.stream, 'release_conn', None)
                if callable(release):
                    release()
