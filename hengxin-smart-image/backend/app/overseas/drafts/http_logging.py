"""Keep signed download URLs and bearer headers out of HTTP library logs."""
import logging


class PrivateTransportFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage().lower()
        return not any(value in message for value in (
            'authorization', 'bearer ', 'token=', 'x-amz-', 'design.qhhengxin.top',
            '.r2.cloudflarestorage.com', '.r2.dev'))


for name in ('httpx', 'httpcore.connection', 'httpcore.http11', 'httpcore.http2', 'httpcore.proxy'):
    logging.getLogger(name).addFilter(PrivateTransportFilter())
