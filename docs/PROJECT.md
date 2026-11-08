# Project record

## Objective

Provide versioned, declared, diffable and reversible Unreal Engine 5.8 render profiles (CVars and scalability) for agents, through a pure core with a thin Unreal adapter.

## Scope

- In scope: profile resolution with `extends` and cycle detection; validation against a whitelisted CVar catalog; diff; apply and revert plans with an automatic snapshot; scalability `DefaultScalability.ini` export; a fake console for tests; packaged example profiles `lumen-lite-6gb`, `balanced` and `trailer-max`.
- Out of scope: automatic optimization, console platform profiles, hardware ray tracing, plugin packaging (.uplugin, Content/Python/, the ToolsetDefinition class and the Unreal smoke test), which is planned for a later supervised session.
- Nothing here was tested inside Unreal. Editor and packaged-game scalability differ.

## Timeline

| Date | Event |
|---|---|
| 2026-11-08 | Specification U803 recorded (origin: planning document, section U803). |

## Effort metrics

| Metric | Value |
|---|---|
| Tokens (input / output) | 620530 / 124569 |
| Time | pending measurement |
| Cost (USD) | 1.0220 |
| Fix rounds | pending measurement |

## Factory run u803 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2379 | 102526 | 0 | 5188 | 0.5155 |
| fix-1 | claude-sonnet-5-5 | no | 6 | 853 | 16575 | 31475 | 0.0531 |
| fix-2 | claude-sonnet-5-5 | no | 4 | 302 | 5573 | 25051 | 0.0195 |
| audit | claude-sonnet-5-5 | no | 16 | 5328 | 49462 | 215822 | 0.1985 |
| fix-3 | claude-sonnet-5-5 | no | 18 | 6277 | 28532 | 230803 | 0.1572 |
| docs | claude-haiku-5-5 | no | 109768 | 9283 | 0 | 0 | 0.0781 |

Total: $1.0220. Prices: Anthropic list prices.
