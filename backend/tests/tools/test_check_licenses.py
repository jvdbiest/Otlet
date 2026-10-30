# SPDX-License-Identifier: AGPL-3.0-or-later
"""tools/check_licenses.py lets compatible licences through and stops the others (B07)."""

import importlib.util
import json
import subprocess
import sys
from collections.abc import Mapping
from email.message import Message
from pathlib import Path
from types import ModuleType

import pytest

CHECK_LICENSES = Path(__file__).resolve().parents[3] / "tools" / "check_licenses.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_licenses", CHECK_LICENSES)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_licenses = load()


@pytest.mark.parametrize(
    "expression",
    [
        "MIT",
        "Apache-2.0 OR BSD-3-Clause",
        "LGPL-3.0-only",
        "(MIT AND BSD-3-Clause)",
        "GPL-3.0-or-later WITH Classpath-exception-2.0",
        "SSPL-1.0 OR MIT",
        "AGPL-3.0-or-later",
    ],
)
def test_compatible_expressions_pass(expression: str) -> None:
    assert check_licenses.allowed_expression(expression)


@pytest.mark.parametrize(
    "expression",
    [
        "SSPL-1.0",
        "BUSL-1.1",
        "Elastic-2.0",
        "GPL-2.0-only",
        "MIT AND SSPL-1.0",
        "UNLICENSED",
        "SEE LICENSE IN LICENSE.md",
    ],
)
def test_incompatible_expressions_fail(expression: str) -> None:
    assert not check_licenses.allowed_expression(expression)


def run_npm(tmp_path: Path, packages: Mapping[str, Mapping[str, object]]) -> int:
    lock = tmp_path / "package-lock.json"
    lock.write_text(json.dumps({"packages": {"": {}, **packages}}), encoding="utf-8")
    return subprocess.run(  # noqa: S603
        [sys.executable, str(CHECK_LICENSES), "npm", str(lock)],
        capture_output=True,
        check=False,
    ).returncode


def test_shipped_sspl_package_fails(tmp_path: Path) -> None:
    packages: dict[str, dict[str, object]] = {
        "node_modules/react": {"license": "MIT"},
        "node_modules/mongo-thing": {"license": "SSPL-1.0"},
    }
    assert run_npm(tmp_path, packages) == 1


def test_dev_only_package_is_not_checked(tmp_path: Path) -> None:
    packages: dict[str, dict[str, object]] = {
        "node_modules/react": {"license": "MIT"},
        "node_modules/build-tool": {"license": "SSPL-1.0", "dev": True},
    }
    assert run_npm(tmp_path, packages) == 0


def test_package_without_licence_fails(tmp_path: Path) -> None:
    assert run_npm(tmp_path, {"node_modules/mystery": {}}) == 1


def test_current_python_environment_passes() -> None:
    assert check_licenses.check_python() == []


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("BSD-3-Clause", "BSD-3-Clause"),
        ("MIT License", "MIT"),
        ("Dual License", None),
        # protobuf and tqdm (ADR-0045).
        ("3-Clause BSD License", "BSD-3-Clause"),
        ("MPL-2.0 AND MIT", "MPL-2.0 AND MIT"),
    ],
)
def test_licence_field_may_hold_a_bare_spdx_identifier(
    monkeypatch: pytest.MonkeyPatch, field: str, expected: str | None
) -> None:
    metadata = Message()
    metadata["Name"] = "package"
    metadata["License"] = field
    monkeypatch.setattr(check_licenses.importlib.metadata, "metadata", lambda name: metadata)
    assert check_licenses.python_licence("package") == expected
