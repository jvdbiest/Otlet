# SPDX-License-Identifier: AGPL-3.0-or-later
"""The import contracts of ADR-0017 hold, and each one rejects a real violation."""

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
LINT_IMPORTS = Path(sys.executable).with_name(
    "lint-imports.exe" if os.name == "nt" else "lint-imports"
)


CONTRACT_NAMES = {
    contract["id"]: contract["name"]
    for contract in tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
        "importlinter"
    ]["contracts"]
}


def run_lint_imports(src: Path) -> subprocess.CompletedProcess[str]:
    # lint-imports prints the contract names, which are in French: force UTF-8 on both
    # sides of the pipe, since Windows defaults to cp1252.
    env = {**os.environ, "PYTHONPATH": str(src), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(  # noqa: S603
        [str(LINT_IMPORTS), "--config", str(BACKEND / "pyproject.toml"), "--no-cache"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_contracts_hold_on_the_real_tree() -> None:
    result = run_lint_imports(BACKEND / "src")
    assert result.returncode == 0, result.stdout + result.stderr


VIOLATIONS = {
    "domain-independence": {"demo/domain/model.py": "import sqlalchemy\n"},
    "module-layers": {
        "demo/application/service.py": "VALUE = 1\n",
        "demo/domain/model.py": "from otlet.demo.application import service\n",
    },
    "entrypoints-on-top": {"demo/application/service.py": "import otlet.entrypoints\n"},
    "ai-sdks-gateway-only": {"demo/application/service.py": "import anthropic\n"},
}


def test_every_contract_has_a_violation_case() -> None:
    assert set(VIOLATIONS) == set(CONTRACT_NAMES)


@pytest.mark.parametrize("contract", sorted(VIOLATIONS))
def test_each_contract_rejects_a_violation(contract: str, tmp_path: Path) -> None:
    src = tmp_path / "src"
    shutil.copytree(BACKEND / "src", src)
    for relative, code in VIOLATIONS[contract].items():
        target = src / "otlet" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
    demo = src / "otlet" / "demo"
    for directory in [demo, *demo.rglob("*")]:
        if directory.is_dir():
            (directory / "__init__.py").touch()

    result = run_lint_imports(src)

    assert result.returncode != 0
    broken = [line for line in result.stdout.splitlines() if line.endswith("BROKEN")]
    assert len(broken) == 1, result.stdout
    assert broken[0].startswith(CONTRACT_NAMES[contract]), result.stdout
