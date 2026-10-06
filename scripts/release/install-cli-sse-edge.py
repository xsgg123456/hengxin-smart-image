"""Install only the conversation SSE location into the existing production edge."""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

CONTAINER = '1Panel-openresty-w177'
CONFIG = '/usr/local/openresty/nginx/conf/conf.d/zhitu.qhhengxin.top.conf'
BLOCK = '''
    # CLI single-image conversation SSE
    location ~ ^/api/v1/api-image-edits/tasks/[^/]+/items/[^/]+/conversation/events/?$ {
        proxy_pass http://127.0.0.1:18080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        gzip off;
        proxy_read_timeout 75s;
    }
'''


def patched(original):
    if BLOCK in original:
        return original
    anchor = '    ssl_prefer_server_ciphers off;\n'
    assert original.count(anchor) == 1
    assert 'server_name zhitu.qhhengxin.top;' in original
    assert original.count('proxy_pass http://127.0.0.1:18080;') == 1
    assert 'conversation/events' not in original
    return original.replace(anchor, anchor + BLOCK, 1)


def main():
    release = sys.argv[1]
    assert re.fullmatch(r'api-edit-20261006-[0-9a-f]{7}', release)
    backup = Path('/opt/hengxin-backups') / release / 'edge-before-sse.conf'
    assert backup.parent.is_dir()
    def run(*args, **kwargs):
        return subprocess.run(['docker', 'exec', '-i', CONTAINER, *args],
                              text=True, check=True, **kwargs)
    def write(content):
        run('sh', '-c', 'cat > "$1"', 'sh', CONFIG, input=content)
    original = run('cat', CONFIG, capture_output=True).stdout
    updated = patched(original)
    if updated == original:
        print('EDGE_SSE_ALREADY_INSTALLED')
        return
    with backup.open('x') as stream:
        stream.write(original)
    backup.chmod(0o600)
    try:
        write(updated)
        run('nginx', '-t')
        run('nginx', '-s', 'reload')
    except BaseException:
        write(original)
        run('nginx', '-t')
        run('nginx', '-s', 'reload')
        raise
    assert run('cat', CONFIG, capture_output=True).stdout == updated
    print('EDGE_SSE_INSTALLED sha256=' + hashlib.sha256(updated.encode()).hexdigest())


if __name__ == '__main__':
    main()
