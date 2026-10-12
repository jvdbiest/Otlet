# SPDX-License-Identifier: AGPL-3.0-or-later
"""tools/check_dco.py accepts signed commits and rejects the others (B04)."""

import subprocess
import sys
from pathlib import Path

import pytest

CHECK_DCO = Path(__file__).resolve().parents[3] / "tools" / "check_dco.py"
AUTHOR = ["-c", "user.name=Ada Lovelace", "-c", "user.email=ada@example.org"]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603
        ["git", "-c", "commit.gpgsign=false", *AUTHOR, *args],  # noqa: S607
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.strip()


def commit(repo: Path, message: str) -> None:
    git(repo, "commit", "--allow-empty", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    commit(tmp_path, "Base\n\nSigned-off-by: Ada Lovelace <ada@example.org>")
    return tmp_path


def check(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(CHECK_DCO), "HEAD~1..HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_accepts_a_commit_signed_by_its_author(repo: Path) -> None:
    git(repo, "commit", "--allow-empty", "-q", "-s", "-m", "Signée avec -s")
    assert check(repo).returncode == 0


def test_accepts_a_sign_off_whatever_the_case_of_the_address(repo: Path) -> None:
    commit(repo, "Signée\n\nSigned-off-by: Ada Lovelace <ADA@Example.org>")
    assert check(repo).returncode == 0


@pytest.mark.parametrize(
    "message",
    [
        "Sans signature",
        "Signée par un autre\n\nSigned-off-by: Charles Babbage <charles@example.org>",
        "Signature dans le corps, pas en trailer Signed-off-by: <ada@example.org>\n\nSuite",
    ],
)
def test_rejects_a_commit_without_its_author_sign_off(repo: Path, message: str) -> None:
    commit(repo, message)
    result = check(repo)
    assert result.returncode == 1
    assert message.splitlines()[0] in result.stdout


def test_accepts_an_unsigned_commit_of_the_update_robot(repo: Path) -> None:
    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=dependabot[bot]",
            "-c",
            "user.email=49699333+dependabot[bot]@users.noreply.github.com",
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            "Dépendances Python : mise à jour",
        ],
        cwd=repo,
        check=True,
    )
    assert check(repo).returncode == 0


def test_rejects_an_unsigned_commit_of_a_lookalike_robot(repo: Path) -> None:
    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=dependabot[bot]",
            "-c",
            "user.email=dependabot@example.org",
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            "Pas le vrai robot",
        ],
        cwd=repo,
        check=True,
    )
    assert check(repo).returncode == 1
