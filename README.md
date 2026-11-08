# ue-render-profiles-toolset

[![PyPI version](https://img.shields.io/pypi/v/trysac-ue-render-profiles-toolset)](https://pypi.org/project/trysac-ue-render-profiles-toolset/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-ue-render-profiles-toolset)](LICENSE)
[![CI](https://github.com/Trysac/u803-ue-render-profiles-toolset/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u803-ue-render-profiles-toolset/actions/workflows/ci.yml)

Pure core and unreal adapter of an Unreal MCP toolset for versioned render profiles (CVars and scalability) with apply, diff, revert and ini export.

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-ue-render-profiles-toolset
# or
uv add trysac-ue-render-profiles-toolset
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import ue_render_profiles_toolset

# normalize() trims surrounding whitespace and lower-cases the text.
print(ue_render_profiles_toolset.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    ue_render_profiles_toolset.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
