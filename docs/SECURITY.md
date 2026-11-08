# Security notes

## Threat model

`trysac-ue-render-profiles-toolset` has no network access and no runtime dependencies. Its only side effects are console reads and writes through the caller-supplied `ue` object and, when explicitly requested, one file write.

### Defended

- **Arbitrary console commands**: the adapter sends only `<cvar> <number>` commands whose CVar name is in the catalog whitelist. Any other command raises `ProfileError` (`invalid_profile`) before it reaches `execute_console_command`.
- **Out-of-range or malformed values**: `apply_profile` runs `ensure_valid` before planning, so a profile with error-level issues is rejected. Values must be finite numbers, integers where the catalog type is `int`, and inside the catalog range.
- **Writes outside the project**: `export_scalability_ini` writes only when `write=True` and `dry_run=False`, only as `DefaultScalability.ini`, and only inside a folder named `Config` that exists. Other paths raise `ProfileError`.
- **Unbounded input**: JSON input is size-limited, the catalog is capped at 512 entries, the profile registry at 64 profiles, and `extends` chains have a depth limit. Error messages are clipped to 200 characters.
- **Silent misconfiguration**: read-back after apply lists any CVar whose value differs from the request under `mismatched`.
- **Unsafe deserialization**: profiles and the catalog are parsed as JSON only. No `eval`, `exec` or pickle is used.

### Not defended

- **A trusted caller**: whoever holds the `ue` object can run any console command directly. This library does not restrict the caller.
- **Persistence of rollback data**: snapshots are kept in memory (at most 16 per store) and are lost when the process exits. A revert after a restart is not possible.
- **Engine-side effects**: the library cannot tell whether a written CVar causes a crash, a driver fault or a performance regression on a given GPU. Read-only and startup CVars are skipped and reported, not verified.
- **Catalog accuracy**: the `source` links point to section-level Epic documentation pages that have not been confirmed. The `scalability_group` mapping is declared by this catalog and must be checked against the project's `BaseScalability.ini`.
- **Behaviour inside Unreal**: the Unreal calls were exercised only against a fake console. The adapter has not been run in the editor.

## Publishing

Release publishing and CI configuration are outside the code reviewed for this document. Do not store long-lived tokens in the repository.
