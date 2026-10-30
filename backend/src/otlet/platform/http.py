# SPDX-License-Identifier: AGPL-3.0-or-later
"""The common outgoing HTTP client, protected against server-side request forgery (SSRF,
ARCHITECTURE §13.2, ASVS V1.3.6, TECH_CHOICES §14).

Every outgoing request of the platform (collection, feed discovery, later images) goes through
`SafeClient`. URLs come from users: without protection they would reach the internal network
of the server. The client therefore:

- accepts HTTP and HTTPS only, on an allow list of ports (80 and 443 by default);
- resolves host names itself, refuses the connection when any resolved address is not public
  (private, loopback, link-local, cloud metadata, shared, reserved, multicast, and their IPv6
  forms), then connects to the address it checked: a second resolution cannot swap it (DNS
  rebinding). This happens at every connection, so at every redirect too;
- follows at most five redirects, each one checked again;
- bounds the duration and the size of every response.

The check sits in the network backend of the connection pool, under the HTTP layer: no code
path opens a connection without it.
"""

import contextlib
import ipaddress
import socket
import ssl
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpcore2
import httpx2
import truststore

from otlet import __version__

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
Resolver = Callable[[str, int], list[str]]

USER_AGENT = f"Otlet/{__version__} (+https://github.com/jvdbiest/Otlet)"
DEFAULT_PORTS = frozenset({80, 443})
MAX_REDIRECTS = 5
CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 10.0
TOTAL_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class FetchError(Exception):
    """An outgoing request failed or was refused. `reason` is a stable code, safe to store and
    to show; the message adds details for the logs."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def is_public(address: IPAddress) -> bool:
    """True for an address of the public Internet. IPv6 forms that embed an IPv4 address
    (mapped, 6to4, Teredo) are judged on the embedded address."""
    if isinstance(address, ipaddress.IPv6Address):
        embedded = address.ipv4_mapped or address.sixtofour
        if embedded is not None:
            return is_public(embedded)
        if address.teredo is not None:
            return is_public(address.teredo[1])
    return address.is_global and not address.is_multicast


@dataclass(frozen=True, slots=True)
class AddressPolicy:
    """Where the client may connect. `allowed_networks` are exceptions to the public-only rule,
    declared by the administrator (a local AI engine, ARCHITECTURE §13.2) or by tests."""

    allowed_networks: tuple[IPNetwork, ...] = ()
    allowed_ports: frozenset[int] = DEFAULT_PORTS

    def permits(self, address: IPAddress) -> bool:
        return is_public(address) or any(address in network for network in self.allowed_networks)


class BlockedAddressError(httpcore2.ConnectError):
    """The policy refused the destination."""


def system_resolver(host: str, port: int) -> list[str]:
    """Every address of `host`, as the system resolves it."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise httpcore2.ConnectError(f"cannot resolve {host}") from error
    return [str(info[4][0]) for info in infos]


class _CuttableStream(httpcore2.NetworkStream):
    """A connection another thread can cut: closing a socket does not wake a thread blocked on
    it, shutting it down does, and the other end sees the connection go."""

    def __init__(self, stream: httpcore2.NetworkStream) -> None:
        self._stream = stream

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return self._stream.read(max_bytes, timeout)

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._stream.write(buffer, timeout)

    def close(self) -> None:
        self._stream.close()

    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore2.NetworkStream:
        self._stream = self._stream.start_tls(ssl_context, server_hostname, timeout)
        return self

    def get_extra_info(self, info: str) -> Any:
        return self._stream.get_extra_info(info)

    def cut(self) -> None:
        connection = self._stream.get_extra_info("socket")
        if connection is not None:
            with contextlib.suppress(OSError):
                connection.shutdown(socket.SHUT_RDWR)


class GuardedBackend(httpcore2.NetworkBackend):
    """Opens TCP connections only to addresses the policy permits (see the module docstring)."""

    def __init__(self, policy: AddressPolicy, resolver: Resolver = system_resolver) -> None:
        self._policy = policy
        self._resolver = resolver
        self._backend = httpcore2.SyncBackend()
        self._opened: list[_CuttableStream] = []

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore2.NetworkStream:
        addresses = [ipaddress.ip_address(a.split("%")[0]) for a in self._addresses(host, port)]
        if not addresses:
            raise httpcore2.ConnectError(f"no address for {host}")
        refused = [address for address in addresses if not self._policy.permits(address)]
        if refused:
            # One forbidden address is enough to refuse: a name that mixes public and internal
            # addresses is an attack, not a configuration.
            raise BlockedAddressError(f"{host} resolves to {refused[0]}")
        stream = _CuttableStream(
            self._backend.connect_tcp(
                str(addresses[0]), port, timeout, local_address, socket_options
            )
        )
        self._opened.append(stream)
        return stream

    def cut_all(self) -> None:
        for stream in self._opened:
            stream.cut()

    def _addresses(self, host: str, port: int) -> list[str]:
        try:
            return [str(ipaddress.ip_address(host.strip("[]")))]
        except ValueError:
            return self._resolver(host, port)

    def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options: Iterable[Any] | None = None
    ) -> httpcore2.NetworkStream:
        raise BlockedAddressError("unix sockets are not allowed")


def _ssl_context() -> ssl.SSLContext:
    # The certificates trusted by the system, like browsers (truststore, a dependency of httpcore2).
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


class SafeTransport(httpx2.HTTPTransport):
    """httpx2's transport over a pool whose every connection goes through GuardedBackend.
    httpx2 does not expose the network backend, so the pool is rebuilt with the same defaults;
    tests/platform/test_http.py proves that connections cannot bypass it."""

    def __init__(self, policy: AddressPolicy, resolver: Resolver = system_resolver) -> None:
        super().__init__(trust_env=False)
        self._backend = GuardedBackend(policy, resolver)
        self._pool = httpcore2.ConnectionPool(
            ssl_context=_ssl_context(),
            network_backend=self._backend,
        )

    def cut(self) -> None:
        """Cuts the connections of this transport, from any thread: the call waiting on them
        fails at once, and the server sees the client go (Ollama stops generating)."""
        self._backend.cut_all()


@dataclass(frozen=True, slots=True)
class FetchResult:
    status: int
    url: str  # after redirects
    headers: Mapping[str, str]
    body: bytes = field(repr=False)

    @property
    def not_modified(self) -> bool:
        return self.status == 304

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    def text(self) -> str:
        charset = "utf-8"
        for parameter in self.headers.get("content-type", "").split(";")[1:]:
            name, _, value = parameter.partition("=")
            if name.strip().lower() == "charset" and value.strip():
                charset = value.strip().strip('"')
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


class SafeClient:
    """Synchronous GET requests under the protections of the module docstring."""

    def __init__(
        self,
        policy: AddressPolicy | None = None,
        *,
        resolver: Resolver = system_resolver,
        user_agent: str = USER_AGENT,
        total_timeout: float = TOTAL_TIMEOUT_SECONDS,
    ) -> None:
        self._policy = policy or AddressPolicy()
        self._total_timeout = total_timeout
        self._client = httpx2.Client(
            transport=SafeTransport(self._policy, resolver),
            follow_redirects=False,
            timeout=httpx2.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
            headers={"User-Agent": user_agent},
            trust_env=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SafeClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def check_url(self, url: str) -> httpx2.URL:
        """The parsed URL, or FetchError when its scheme or port is not allowed. The host is
        checked when connecting, after resolution."""
        try:
            parsed = httpx2.URL(url)
        except (httpx2.InvalidURL, TypeError) as error:
            raise FetchError("invalid_url", str(error)) from error
        if parsed.scheme not in ("http", "https"):
            raise FetchError("scheme_not_allowed", parsed.scheme)
        if not parsed.host:
            raise FetchError("invalid_url", "no host")
        if parsed.userinfo:
            raise FetchError("invalid_url", "credentials in the URL")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in self._policy.allowed_ports:
            raise FetchError("port_not_allowed", str(port))
        return parsed

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> FetchResult:
        deadline = time.monotonic() + self._total_timeout
        current = self.check_url(url)
        for _ in range(MAX_REDIRECTS + 1):
            try:
                with self._client.stream("GET", current, headers=headers) as response:
                    if response.status_code in REDIRECT_STATUSES and "location" in response.headers:
                        current = self.check_url(str(current.join(response.headers["location"])))
                        continue
                    body = self._read(response, max_bytes, deadline)
                    return FetchResult(
                        status=response.status_code,
                        url=str(current),
                        headers={k.lower(): v for k, v in response.headers.items()},
                        body=body,
                    )
            except httpx2.TimeoutException as error:
                raise FetchError("timeout", str(error)) from error
            except httpx2.HTTPError as error:
                if isinstance(error.__cause__, BlockedAddressError):
                    raise FetchError("address_not_allowed", str(error.__cause__)) from error
                raise FetchError("network_error", str(error)) from error
        raise FetchError("too_many_redirects", url)

    @staticmethod
    def _read(response: httpx2.Response, max_bytes: int, deadline: float) -> bytes:
        declared = response.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > max_bytes:
            raise FetchError("too_large", declared)
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > max_bytes:
                raise FetchError("too_large", f"more than {max_bytes} bytes")
            if time.monotonic() > deadline:
                raise FetchError("timeout", "total duration exceeded")
            chunks.append(chunk)
        return b"".join(chunks)
