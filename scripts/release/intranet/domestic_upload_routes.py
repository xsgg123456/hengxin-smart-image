"""Render the domestic studio upload exception in the LAN gateway configuration."""

BODY_LIMIT = 500_000_000 + 65_536
GENERIC = b'    location /api/ {\n'
UPLOAD = (
    b'    location ~ ^/api/v1/domestic-studio/'
    b'(?:tasks/[^/]+/studio|workspaces/[^/]+)/files/?$ {\n'
)


def render(original: bytes) -> bytes:
    if (original.count(GENERIC) != 1 or original.count(b'    client_max_body_size 10m;\n') != 1
            or UPLOAD in original):
        raise ValueError('Expected the original domestic gateway API location')
    start = original.index(GENERIC)
    end = original.index(b'    }\n', start) + len(b'    }\n')
    generic = original[start:end]
    timeout = b'        proxy_read_timeout 75s;\n'
    if (generic.count(timeout) != 1 or b'        set $upstream http://domestic-api:8000;\n' not in generic
            or b'        proxy_http_version 1.1;\n' not in generic or b'        proxy_pass $upstream;\n' not in generic):
        raise ValueError('Unexpected domestic upstream or proxy settings')
    # Inherit the generic route's upstream and forwarding headers; keep the
    # generic block itself byte-identical for every other domestic API request.
    limits = (f'        client_max_body_size {BODY_LIMIT};\n'.encode()
              + b'        client_body_timeout 300s;\n'
              + b'        proxy_send_timeout 300s;\n'
              + b'        proxy_read_timeout 300s;\n'
              + b'        proxy_request_buffering off;\n')
    upload = generic.replace(GENERIC, UPLOAD, 1).replace(timeout, limits, 1)
    return original[:start] + upload + b'\n' + original[start:]
