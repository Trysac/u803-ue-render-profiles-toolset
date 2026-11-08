# Stack

## Used

| Tool | Why |
|---|---|
| Python 3.11 or newer | Runtime requirement stated in the README; the library uses only the standard library at runtime. |
| uv | Fast, reproducible environments and builds on Windows and Linux. |
| hatchling | Simple, standards-based build backend; no setup.py. |
| ruff | Lint and format in one fast tool. |
| mypy (strict) | Catches type errors before release; the package ships `py.typed`. |
| pytest + pytest-cov | Test runner with branch coverage. |
| Hypothesis (dev only, >=6.100,<7) | Property tests for merge, apply and revert, derandomized. |
| gitleaks | Secret scanning locally and in CI. |
| GitHub Actions + Dependabot | CI wrapper over the local gates; weekly dependency updates. |

## Runtime dependencies

None. The core and adapter import only the Python standard library.

## Discarded

| Tool | Why not |
|---|---|
| Poetry | Slower, and uv covers the same needs with standard dependency groups. |
| black + isort + flake8 | Replaced by ruff: one tool instead of three. |
| tox / nox | The OS matrix lives in CI; locally a single `scripts/check.py` is enough. |
| Shell scripts for gates | Not portable to Windows; the gates are a stdlib Python script. |
