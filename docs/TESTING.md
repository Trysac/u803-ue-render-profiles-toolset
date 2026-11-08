# Testing

## Running

```sh
uv run pytest --cov=ue_render_profiles_toolset   # tests with coverage report
uv run python scripts/check.py                    # every gate, as CI and the factory run it
```

## Policy

- Branch coverage of `src/ue_render_profiles_toolset` must stay at or above 85 %; the gate fails below it.
- Tests exercise the public API (`import ue_render_profiles_toolset`) and assert observable effects: return values, raised `ProfileError` codes and messages, and the console commands sent to the fake.
- Each bug fix starts with a failing test that reproduces it.
- Tests are deterministic: no network, no wall clock, no dependence on test order. Hypothesis properties run with `derandomize=True`.

## What the suite covers

The specification defines these tests; check them against the `tests/` folder before relying on a specific file name.

- `resolve_profile`: child values override parent values key by key; a cycle such as a -> b -> a raises `extends_cycle`.
- `validate_profile`: a CVar not in `catalog/cvars.json` is reported as `unknown_cvar`, not silently ignored.
- `diff_profiles`: `balanced` against `trailer-max` lists every differing CVar with both values and the impact note.
- `apply_profile` with `dry_run=True` on the fake console executes 0 commands and lists the plan.
- Apply with `dry_run=False` followed by `revert_last`: every whitelisted CVar equals its snapshot value.
- Every generated command names a whitelisted CVar.
- A read-back of `r.ScreenPercentage` as 75 after 100 was requested is listed under `mismatched`.
- `export_scalability_ini` for Low, Medium and High equals the golden file `tests/fixtures/golden/DefaultScalability.ini`, and a check confirms its file name matches the literal `tests/golden/DefaultScalability.ini` named in the specification.
- `export_scalability_ini` with `write=True` and `dry_run=True` writes 0 files.
- Property tests (Hypothesis, derandomized): merge is associative by levels; apply then revert restores the snapshot; no command falls outside the whitelist.

The fake console used by these tests is `tests/fakes/unreal.py`. None of these tests run inside Unreal.

## Tiers

- Local tier (every gate run, coverage measured here): unit and property tests, plus conformance on small fixtures kept in the repository.
- CI tier: conformance that needs an external tool or a download. These are marked `@pytest.mark.conformance`; `scripts/check.py` deselects them locally unless `FABRICA_CI=1` is set.

## Layout

`tests/test_<module>.py` mirrors each public module. Shared fixtures go in `tests/conftest.py`. The fake console lives in `tests/fakes/`, and golden files live under `tests/fixtures/`.
