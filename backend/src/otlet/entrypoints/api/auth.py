# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sign-in endpoints and the session and CSRF dependencies of the API (F02, ADR-0029).

- The session lives in a `__Host-` cookie: Secure, HttpOnly, SameSite=Strict, path /.
- Every state-changing request is refused when the browser says it comes from another site
  (Fetch Metadata), and every authenticated one must also carry the CSRF token, derived from
  the session and returned by /api/auth/session.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from otlet.identity.application.authentication import (
    Authentication,
    ReauthenticationRequired,
    SignedIn,
)
from otlet.identity.domain import model
from otlet.identity.domain.model import InvalidCredentials, Session, TooManyAttempts, WeakPassword

COOKIE = "__Host-otlet_session"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class Credentials(BaseModel):
    login: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=model.PASSWORD_MAX_LENGTH)


class Password(BaseModel):
    password: str = Field(min_length=1, max_length=model.PASSWORD_MAX_LENGTH)


class NewPassword(BaseModel):
    new_password: str = Field(min_length=1, max_length=model.PASSWORD_MAX_LENGTH)


class UserView(BaseModel):
    id: str
    display_name: str
    is_instance_admin: bool


class SessionView(BaseModel):
    user: UserView
    csrf_token: str


def same_origin(request: Request) -> None:
    """Refuses state-changing requests that the browser marks as coming from another site."""
    if request.method in SAFE_METHODS:
        return
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross_site_request")


def build_router(auth: Authentication) -> tuple[APIRouter, Callable[..., Session]]:
    """The /api/auth routes, and the dependency that other routes use to require a session."""

    def current_session(request: Request) -> Session:
        token = request.cookies.get(COOKIE)
        session = auth.resolve(token) if token else None
        if session is None or token is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
        if request.method not in SAFE_METHODS and not model.csrf_matches(
            token, request.headers.get(CSRF_HEADER)
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "csrf_token_invalid")
        request.state.session_token = token
        return session

    CurrentSession = Annotated[Session, Depends(current_session)]
    router = APIRouter(prefix="/api/auth", dependencies=[Depends(same_origin)])

    def view(session: Session, token: str) -> SessionView:
        user = auth.user(session)
        return SessionView(
            user=UserView(
                id=str(user.id),
                display_name=user.display_name,
                is_instance_admin=user.is_instance_admin,
            ),
            csrf_token=model.csrf_token(token),
        )

    @router.post("/login")
    def login(credentials: Credentials, request: Request, response: Response) -> SessionView:
        client = request.client.host if request.client else "unknown"
        try:
            signed_in: SignedIn = auth.sign_in(
                credentials.login,
                credentials.password,
                client,
                request.headers.get("user-agent"),
            )
        except TooManyAttempts as error:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "too_many_attempts",
                headers={"Retry-After": str(int(error.retry_after.total_seconds()))},
            ) from error
        except InvalidCredentials as error:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials") from error
        response.set_cookie(
            COOKIE,
            signed_in.token,
            max_age=int(model.SESSION_LIFETIME.total_seconds()),
            path="/",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        return view(signed_in.session, signed_in.token)

    @router.get("/session")
    def current(session: CurrentSession, request: Request) -> SessionView:
        return view(session, request.state.session_token)

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(session: CurrentSession, response: Response) -> None:
        auth.sign_out(session)
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")

    @router.post("/reauthenticate", status_code=status.HTTP_204_NO_CONTENT)
    def reauthenticate(body: Password, session: CurrentSession) -> None:
        try:
            auth.reauthenticate(session, body.password)
        except InvalidCredentials as error:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials") from error

    @router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
    def change_password(body: NewPassword, session: CurrentSession) -> None:
        try:
            auth.change_password(session, body.new_password)
        except ReauthenticationRequired as error:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "reauthentication_required") from error
        except WeakPassword as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    return router, current_session
