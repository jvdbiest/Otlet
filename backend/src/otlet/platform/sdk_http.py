# SPDX-License-Identifier: AGPL-3.0-or-later
"""The guarded HTTP client handed to the SDKs of AI providers (F05, ADR-0027).

The address of a provider is entered by a user: the protections of `SafeClient` apply
(ARCHITECTURE §13.2). The `openai` and `anthropic` SDKs speak through `httpx2`, so they get the
same `SafeTransport`, whose every connection checks the resolved address, plus a check of each
request: HTTP or HTTPS only, no credentials in the URL, a port the policy allows (80 and 443,
plus those the administrator adds for a local engine such as Ollama on 11434). No redirect is
followed.
"""

import httpx2

from otlet.platform.http import AddressPolicy, BlockedAddressError, Resolver, SafeTransport
from otlet.platform.http import system_resolver as default_resolver


class EndpointRefused(BlockedAddressError):
    """The policy refused the provider's scheme, credentials or port."""


def check_endpoint(url: httpx2.URL, policy: AddressPolicy) -> None:
    if url.scheme not in ("http", "https"):
        raise EndpointRefused(f"scheme {url.scheme} is not allowed")
    if url.userinfo:
        raise EndpointRefused("credentials in the URL")
    port = url.port or (443 if url.scheme == "https" else 80)
    if port not in policy.allowed_ports:
        raise EndpointRefused(f"port {port} is not allowed")


def guarded_sdk_client(
    policy: AddressPolicy, timeout_seconds: float, resolver: Resolver = default_resolver
) -> httpx2.Client:
    def check(request: httpx2.Request) -> None:
        check_endpoint(request.url, policy)

    return httpx2.Client(
        transport=SafeTransport(policy, resolver),
        timeout=timeout_seconds,
        follow_redirects=False,
        trust_env=False,
        event_hooks={"request": [check]},
    )


def refused(error: BaseException) -> bool:
    """True when the policy refused the destination somewhere in the chain of `error`."""
    cause: BaseException | None = error
    while cause is not None:
        if isinstance(cause, BlockedAddressError):
            return True
        cause = cause.__cause__ or cause.__context__
    return False
