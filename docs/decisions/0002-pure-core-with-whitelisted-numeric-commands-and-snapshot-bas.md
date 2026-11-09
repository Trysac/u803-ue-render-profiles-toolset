# Pure core with whitelisted numeric commands and snapshot-based revert

Status: accepted (generated, pending human review); snapshot persistence amended by ADR 0003

## Context

Tuning Unreal Engine rendering by typing console variables leaves no record and no safe revert. An agent-facing toolset must be diffable and reversible, must be testable without Unreal, and must never send arbitrary console commands.

## Decision

Keep all logic in a stdlib-only core that never imports unreal: profile resolution with cycle and depth limits, validation against a packaged CVar catalog, diff, apply and revert plans, and ini rendering. The catalog keys are the only command whitelist and commands have the single shape '<cvar> <number>'. A thin adapter takes the unreal module as an argument, reads values with SystemLibrary, writes with execute_console_command, stores a bounded in-memory snapshot of the CVars an apply touched, and reverts exactly those CVars. Read-only CVars are skipped and sg.* groups are applied first. File writes require write=True and dry_run=False and target only DefaultScalability.ini inside a Config folder.

## Consequences

The core and adapter are fully testable against a fake console, and every claim (whitelist, exact revert, read-back mismatches) is covered by tests and Hypothesis properties. Snapshots are lost when the editor restarts. The adapter's Unreal API calls are verified only against the fake and need a supervised smoke test inside Unreal. The catalog-declared scalability groups used by the ini export must be reviewed against a project's BaseScalability.ini.
