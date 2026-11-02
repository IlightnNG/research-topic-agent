# RESULTS · Phase 4.2 S0–S2

> Status: S0/S1/S2 done
> Date: 2026-11-02
> Scope: baseline, tool contracts, ToolRuntime

---

## S0 · Baseline

Before Phase 4.2 changes:

```text
84 passed (LIT_V2_LIVE)
ruff clean
```

The Phase 4.1 report chain remains intact.

---

## S1 · Tool contracts

Extended `contracts/tool.py`:

```text
ToolSpec:
  namespace
  title
  version

  parallel_safe
  requires_approval
  max_output_chars
  capabilities
  tags
  render

ToolContext:
  run_id / node_id / call_id
  workspace
  signal
  events
  artifacts

ToolError:
  code / message / retryable / details

ToolResult:
  content
  error
  artifact_refs
  truncated
```

Kept backward compatibility:

```text
handler(args) -> dict
existing ToolSpec positional usage
existing ToolResult positional usage
```

`parallel_safe`:

```text
None  -> derive from side_effect
True  -> explicitly parallel-safe
False -> exclusive
```

`ToolRegistry` now validates `output_schema` before returning success:

```text
E_TOOL_OUTPUT_SCHEMA
```

---

## S2 · ToolRuntime

New:

```text
tools/runtime.py
tools/sets.py
```

`ToolRuntime` provides:

```text
toolset visibility
default toolset
policy before dispatch
render content
oversized content spill to artifact
structured policy denial
unknown tool / not-allowed tool
```

Tool sets:

```text
GENERAL_TOOLSET
SOURCE_TOOLSET
EVIDENCE_TOOLSET
REPORT_TOOLSET
CHAT_TOOLSET
```

Runtime contract:

```python
runtime.specs(toolset)
runtime.visible(toolset)
runtime.allows(name, toolset)
runtime.call(name, args, toolset=..., context=...)
```

Policy:

```python
policy(name, args, context) -> True | False | str
```

Denied calls:

```text
E_TOOL_POLICY_DENIED
```
Most important: ToolRuntime is a scoped view, not a second registry.

---

## Tests

```text
tests/v2/test_tool_runtime.py
  7 tests
```

Coverage:

```text
parallel_safe defaults
output schema validation
toolset visibility
not-allowed tool
policy denial
render + artifact spill
unknown toolset
```

Full suite:

```text
91 passed
ruff clean
```

---

## Files

```text
src/lit_agent_v2/contracts/tool.py
src/lit_agent_v2/tools/schema.py
src/lit_agent_v2/tools/registry.py
src/lit_agent_v2/tools/runtime.py
src/lit_agent_v2/tools/sets.py
src/lit_agent_v2/tools/__init__.py
tests/v2/test_tool_runtime.py
docs/CONTRACTS.md
```

---

## Not done

```text
General tools are not implemented yet:
  context.inspect / context.compact
  plan.* / memory.* / test.run / verify.*

Kernel does not consume ToolRuntime yet.
Policy is not wired into Kernel.
ToolContext is not passed to handlers yet.
Repair loop is not implemented.
```

These belong to S3/S4.

---

## Next

```text
S3 = 4.2.3 General tools
S4 = 4.2.4 Generic Kernel
S5 = Kernel A–E acceptance
S6 = Workflow core + report shell
```
