# Include inside the existing /api/overseas/v1/ location on every HTTP proxy hop.
# 500 MB file plus the backend's 64 KiB multipart envelope; domestic stays unchanged.
client_max_body_size 500065536;
client_body_timeout 300s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;
proxy_http_version 1.1;
proxy_request_buffering off;
