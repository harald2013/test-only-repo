import threading
from http.client import HTTPConnection
from http.server import HTTPServer

import pytest

from app import BODY, CONTENT_TYPE, HEALTH_BODY, Handler


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    thread.join(timeout=5)
    httpd.server_close()


def test_get_returns_hello_world(server):
    host, port = server.server_address
    connection = HTTPConnection(host, port, timeout=5)
    connection.request("GET", "/")
    response = connection.getresponse()

    assert response.status == 200
    assert response.getheader("Content-Type") == CONTENT_TYPE
    assert response.read() == BODY


def test_health_returns_ok(server):
    host, port = server.server_address
    connection = HTTPConnection(host, port, timeout=5)
    connection.request("GET", "/health")
    response = connection.getresponse()

    assert response.status == 200
    assert response.getheader("Content-Type") == CONTENT_TYPE
    assert response.read() == HEALTH_BODY
