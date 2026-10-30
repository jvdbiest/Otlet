# SPDX-License-Identifier: AGPL-3.0-or-later
"""The common HTTP client refuses internal destinations (U01, ARCHITECTURE §13.2, ASVS V1.3.6).

A real server listens on 127.0.0.1. The tests that must reach it allow that single address
explicitly; every other test runs under the default policy, which allows public addresses only.
"""

import ipaddress
import socket
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx2
import pytest

from otlet.platform.http import AddressPolicy, FetchError, SafeClient, SafeTransport, is_public

LOCAL = ipaddress.ip_network("127.0.0.1/32")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server's naming)
        port = int(self.server.server_address[1])  # type: ignore[index]
        routes = {
            "/ok": (200, {"Content-Type": "text/plain; charset=utf-8"}, b"bonjour"),
            "/big": (200, {}, b"x" * 2048),
            "/to-metadata": (302, {"Location": "http://169.254.169.254/latest/"}, b""),
            "/to-ok": (301, {"Location": "/ok"}, b""),
            "/to-file": (302, {"Location": "file:///etc/passwd"}, b""),
            "/loop": (302, {"Location": "/loop"}, b""),
            "/to-other-port": (302, {"Location": f"http://127.0.0.1:{port + 1}/"}, b""),
        }
        status, headers, body = routes.get(self.path, (404, {}, b""))
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def server() -> Iterator[int]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()


def local_client(port: int) -> SafeClient:
    return SafeClient(AddressPolicy(allowed_networks=(LOCAL,), allowed_ports=frozenset({port})))


def refusal(client: SafeClient, url: str) -> str:
    with pytest.raises(FetchError) as caught:
        client.get(url)
    return caught.value.reason


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.129.252",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",  # noqa: S104 (an address under test, not a binding)
        "224.0.0.1",
        "255.255.255.255",
        "::1",
        "fe80::1",
        "fd00:ec2::254",
        "::ffff:127.0.0.1",
        "2002:7f00:1::",
        "::",
    ],
)
def test_internal_addresses_are_not_public(address: str) -> None:
    assert not is_public(ipaddress.ip_address(address))


@pytest.mark.parametrize("address", ["93.184.215.14", "2606:4700:4700::1111", "1.1.1.1"])
def test_internet_addresses_are_public(address: str) -> None:
    assert is_public(ipaddress.ip_address(address))


def test_the_allowed_destination_answers(server: int) -> None:
    with local_client(server) as client:
        result = client.get(f"http://127.0.0.1:{server}/ok")
    assert (result.status, result.text()) == (200, "bonjour")


def test_loopback_is_refused_by_default(server: int) -> None:
    policy = AddressPolicy(allowed_ports=frozenset({server}))
    with SafeClient(policy) as client:
        assert refusal(client, f"http://127.0.0.1:{server}/ok") == "address_not_allowed"
        assert refusal(client, f"http://[::ffff:127.0.0.1]:{server}/ok") == "address_not_allowed"


def test_a_name_resolving_to_an_internal_address_is_refused(server: int) -> None:
    policy = AddressPolicy(allowed_ports=frozenset({server}))
    with SafeClient(policy, resolver=lambda host, port: ["127.0.0.1"]) as client:
        assert refusal(client, f"http://feeds.example.org:{server}/ok") == "address_not_allowed"


def test_one_internal_address_among_public_ones_is_enough_to_refuse() -> None:
    resolver = lambda host, port: ["93.184.215.14", "10.0.0.7"]  # noqa: E731
    with SafeClient(resolver=resolver) as client:
        assert refusal(client, "http://rebind.example.org/") == "address_not_allowed"


def test_the_checked_address_is_the_one_connected_to(server: int) -> None:
    """The client connects to the address it checked, without resolving the name a second
    time (DNS rebinding): feeds.example.org does not exist outside this resolver."""
    calls: list[str] = []

    def resolver(host: str, port: int) -> list[str]:
        calls.append(host)
        return ["127.0.0.1"]

    policy = AddressPolicy(allowed_networks=(LOCAL,), allowed_ports=frozenset({server}))
    with SafeClient(policy, resolver=resolver) as client:
        assert client.get(f"http://feeds.example.org:{server}/ok").status == 200
    assert calls == ["feeds.example.org"]


def test_a_redirect_to_cloud_metadata_is_refused(server: int) -> None:
    with local_client(server) as client:
        assert refusal(client, f"http://127.0.0.1:{server}/to-metadata") == "port_not_allowed"
    policy = AddressPolicy(allowed_networks=(LOCAL,), allowed_ports=frozenset({server, 80}))
    with SafeClient(policy) as client:
        assert refusal(client, f"http://127.0.0.1:{server}/to-metadata") == "address_not_allowed"


def test_redirects_are_followed_and_checked(server: int) -> None:
    with local_client(server) as client:
        result = client.get(f"http://127.0.0.1:{server}/to-ok")
        assert (result.status, result.url) == (200, f"http://127.0.0.1:{server}/ok")
        assert refusal(client, f"http://127.0.0.1:{server}/to-file") == "scheme_not_allowed"
        assert refusal(client, f"http://127.0.0.1:{server}/loop") == "too_many_redirects"
        assert refusal(client, f"http://127.0.0.1:{server}/to-other-port") == "port_not_allowed"


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("file:///etc/passwd", "scheme_not_allowed"),
        ("gopher://example.org/", "scheme_not_allowed"),
        ("ftp://example.org/feed", "scheme_not_allowed"),
        ("http://example.org:6379/", "port_not_allowed"),
        ("https://user:secret@example.org/", "invalid_url"),
        ("http:///nohost", "invalid_url"),
    ],
)
def test_only_http_on_allowed_ports(url: str, reason: str) -> None:
    with SafeClient() as client:
        assert refusal(client, url) == reason


def test_the_size_is_bounded(server: int) -> None:
    with local_client(server) as client:
        with pytest.raises(FetchError) as caught:
            client.get(f"http://127.0.0.1:{server}/big", max_bytes=1024)
    assert caught.value.reason == "too_large"


def test_a_connection_cut_from_another_thread_wakes_the_call_and_the_server_sees_it() -> None:
    listener = socket.create_server(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    ended: list[bytes] = []

    def serve() -> None:
        connection, _ = listener.accept()
        connection.recv(65536)  # the request; no answer is ever sent
        ended.append(connection.recv(65536))  # b"": the client went
        connection.close()

    threading.Thread(target=serve, daemon=True).start()
    transport = SafeTransport(
        AddressPolicy(
            allowed_networks=(ipaddress.ip_network("127.0.0.0/8"),),
            allowed_ports=frozenset({port}),
        )
    )
    failure: list[BaseException] = []

    def call() -> None:
        try:
            with httpx2.Client(transport=transport, timeout=30, trust_env=False) as client:
                client.get(f"http://127.0.0.1:{port}/")
        except httpx2.TransportError as error:
            failure.append(error)

    caller = threading.Thread(target=call, daemon=True)
    caller.start()
    deadline = time.monotonic() + 5
    while not transport._backend._opened and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.1)
    transport.cut()
    caller.join(5)
    assert not caller.is_alive() and failure
    for _ in range(100):
        if ended:
            break
        time.sleep(0.05)
    assert ended == [b""]
    listener.close()
