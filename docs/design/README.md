# Design Docs

> Status: frontend F1–F6 complete; Phase 4.1.7 real API integration complete.
> Scope: Vue 3 frontend, local development, trajectory UX rules.

---

## Documents

| Document | Role | When to update |
|---|---|---|
| [FRONTEND.md](FRONTEND.md) | authoritative frontend product/layout/component/API design | when layout, routes, components, contracts, or UX rules change |
| [DEV-RUNBOOK.md](DEV-RUNBOOK.md) | commands to start backend/frontend and manually test | when ports, env vars, startup, or smoke-test steps change |
| [TRAJECTORY-UX.md](TRAJECTORY-UX.md) | trajectory rendering rules and fixed issues | when run trace, tool cards, compaction, or failure display changes |

---

## Current Status

```text
F1  Topics / Topic modal / Report-Chat switch          done
F2  Report shell / Run list / New Run / Tabs            done
F3  Trajectory / progress / pause-resume                done
F4  Report / citations / paper tabs                     done
F5  Chat / streaming / stop / delete                    done
F6  Inspector / citations / authors placeholder         done
```

Backend integration:

```text
real API mode: VITE_USE_MOCK=false
topics / runs / trace / report / paper / chat
```

Known limits:

```text
pause/resume is step-boundary based
real chat has no token streaming (mock has streaming)
PDF is iframe + metadata fallback
topic normalization is deterministic, not LLM
```

---

## Canonical Paths

```text
web/                       Vue app
web/README.md              frontend quick start
docs/design/FRONTEND.md    design spec
docs/design/DEV-RUNBOOK.md startup + manual test
docs/design/TRAJECTORY-UX.md trajectory UX record
```

---

## Maintenance Rules

```text
do not create another frontend design doc
add new design rules to FRONTEND.md
add operational commands to DEV-RUNBOOK.md
add trajectory behavior changes to TRAJECTORY-UX.md
keep status sections synchronized
```
