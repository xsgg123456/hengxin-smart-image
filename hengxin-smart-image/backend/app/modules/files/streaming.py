from fastapi.responses import StreamingResponse


class OwnedStreamResponse(StreamingResponse):
    """Own the HTTP connection even if the client disconnects before iteration starts."""
    def __init__(self, stream, **kwargs):
        self.stream = stream
        super().__init__(stream.stream(64 * 1024), **kwargs)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                self.stream.close()
            finally:
                self.stream.release_conn()
