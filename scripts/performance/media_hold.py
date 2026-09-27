"""Slow clients inside the isolated Docker network, bypassing Desktop forwarding."""
import json
import socket
import sys
from http.client import HTTPConnection


data = json.loads(sys.stdin.readline())
connections = []
try:
    statuses = []
    for index in range(data['count']):
        conn = HTTPConnection('web', 80, timeout=40)
        # Set the window BEFORE the handshake, not after TCP window negotiation.
        conn.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.sock.settimeout(40)
        conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        conn.sock.connect(('web', 80))
        conn.request('GET', data['path'], headers={'Cookie': data['cookie']})
        response = conn.getresponse()
        connections.append((conn, response))
        statuses.append(response.status)
    print(json.dumps(statuses), flush=True)
    sys.stdin.readline()
finally:
    for conn, response in connections:
        response.close()
        conn.close()
