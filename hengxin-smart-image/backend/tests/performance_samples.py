"""Isolated HTTP measurements; these are not browser timings or production p95."""
import re
from time import perf_counter


def sample(client, path):
    started = perf_counter()
    response = client.get(path)
    elapsed_ms = (perf_counter() - started) * 1000
    assert response.status_code == 200, response.text
    timing = response.headers.get('server-timing', '')
    queries = re.search(r'sql;desc="(\d+)"', timing)
    app_time = re.search(r'app;dur=([\d.]+)', timing)
    assert queries and app_time, 'baseline requires request-local Server-Timing'
    return response, {
        'path': path, 'status': response.status_code,
        'sql_before_headers': int(queries[1]),
        'app_before_headers_ms': float(app_time[1]),
        'testclient_roundtrip_ms': round(elapsed_ms, 3),
        'uncompressed_body_bytes': len(response.content),
    }


def image_budget(client, pictures):
    urls = sorted({picture['url'] for picture in pictures})
    results = [sample(client, url) for url in urls]
    return {
        'unique_images': len(results),
        'original_bytes': sum(len(response.content) for response, _ in results),
        'image_sql': sum(row['sql_before_headers'] for _, row in results),
    }
