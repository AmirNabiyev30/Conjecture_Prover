# Building the Lean workspace from a fresh clone

This repository does not track its Lean scaffold, so a fresh clone contains the
Python agent but **no buildable Lean project yet**. This document describes what
is missing, how to create it, and the one invariant that must hold.

If you just want to run the Python unit tests, you do not need any of this:

```bash
cd LangGraph && uv sync && uv run python -m pytest tests/unit_tests
```

---

## What is deliberately not tracked

| Path | Why | Who creates it |
| --- | --- | --- |
| `lakefile.toml` | Names the Lake library, so it is checkout-specific | You (step 3) |
| `lean-toolchain` | The Lean version pin | You (step 2) |
| `lake-manifest.json` | Dependency lock, written by `lake` | `lake` |
| `<WORKSPACE_NAME>` (default `ConjectureProver.lean`) | The file the agent edits; the harness overwrites it at the start of every run and archives a copy under `experiment_runs/artifacts/<run_id>/` | You (step 4), then the harness |
| `Main.lean` | `lean_exe` root belonging to `lakefile.toml` | You (step 5) |
| `.lake/`, `mathlib4/` | Vendored dependencies and build output | `lake` |
| `LangGraph/.venv` | Python environment | `uv sync` |
| `experiment_runs/{logs,artifacts,backup,summaries}/` | Per-run scratch; regenerated every run | The harness |

The tracked study record is `experiment_runs/results.csv` and `results.jsonl`.

---

## The invariant: one name, three places

> **The workspace filename, the `[[lean_lib]]` name, and `WORKSPACE_NAME` must
> all be the same name.**

Lean derives a module's name from the library it belongs to. `lake build
:blueprintJson` then writes its output to:

```
.lake/build/blueprint/module/<module>.json
```

The Python side locates that file using `config.WORKSPACE_MODULE`, which is
derived from `WORKSPACE_NAME` by dropping the `.lean` extension. So if the three
names disagree, the blueprint lookup points at a file Lake never produces and the
run fails with a `FileNotFoundError`.

Pick a name — call it `<Module>` — and use it consistently. This repository's
default is `ConjectureProver`.

---

## 1. Prerequisites

- [elan](https://github.com/leanprover/elan) for the Lean toolchain
- `uv` for the Python environment (Python 3.12)
- Roughly 8 GB of disk for Mathlib and its build cache

## 2. Pin the Lean toolchain

Create `lean-toolchain`:

```
leanprover/lean4:v4.33.0-rc1
```

This must match the `repl` revision in the next step — the `repl` package is
built against a specific Lean version, and a mismatch fails at build time.

## 3. Create `lakefile.toml`

```toml
name = "lean-workspace"
version = "0.1.0"
defaultTargets = ["lean-workspace"]

[[lean_lib]]
name = "<Module>"          # must match WORKSPACE_NAME and the workspace filename

[[require]]
name = "LeanArchitect"
git = "https://github.com/hanwenzhu/LeanArchitect.git"
rev = "main"

[[require]]
name = "mathlib"
scope = "leanprover-community"

[[require]]
name = "checkdecls"
git = "https://github.com/PatrickMassot/checkdecls.git"

[[require]]
name = "«doc-gen4»"
git = "https://github.com/leanprover/doc-gen4"
rev = "main"

[[require]]
name = "repl"
git = "https://github.com/leanprover-community/repl"
rev = "v4.33.0-rc1"        # must match lean-toolchain

[[lean_exe]]
name = "lean-workspace"
root = "Main"
```

`LeanArchitect` is what supplies the `@[blueprint]` attribute, the dependency
inference, and the `lake build :blueprintJson` export that the Python side
parses. Without it the agent has no dependency graph to reason over.

## 4. Create the workspace file

Create `<Module>.lean` at the repository root:

```lean
import Mathlib
import Architect
```

That is enough — the harness replaces this file with the problem statement at the
start of each run (`WORKSPACE.write_text(header_comment + problem_source)`) and
restores the previous contents afterwards. Give it a real formalization only if
you want one to survive between runs.

## 5. Create the executable entry point

`lakefile.toml` declares `[[lean_exe]] root = "Main"`, so create `Main.lean`:

```lean
def main : IO Unit := do
  IO.println "Hello, world!"
```

## 6. Fetch Mathlib and build

```bash
lake exe cache get    # prebuilt Mathlib oleans; avoids a multi-hour compile
lake build            # builds <Module> and the :blueprintJson exporter
```

## 7. Set up the Python agent

```bash
cd LangGraph
uv sync
```

## 8. Tell the agent which module to use

`WORKSPACE_NAME` defaults to `ConjectureProver.lean`. If you chose a different
`<Module>`, export it — both the agent and the experiment harness read this one
setting:

```bash
export WORKSPACE_NAME=<Module>.lean
```

Verify the three names agree before running anything:

```bash
cd LangGraph
PYTHONPATH=src/agent .venv/bin/python -c \
  "import config; print(config.WORKSPACE_NAME, '->', config.WORKSPACE_MODULE)"
```

## 9. Sanity check

```bash
# Python side: the unit suite needs no Lean toolchain
cd LangGraph && .venv/bin/python -m pytest tests/unit_tests

# Harness: seeds the workspace, runs nothing, restores it
cd .. && PYTHONPATH=LangGraph/src/agent LangGraph/.venv/bin/python -m \
  experiments.runner --list
PYTHONPATH=LangGraph/src/agent LangGraph/.venv/bin/python -m \
  experiments.runner --only with_analyzer__fateX_94 --dry-run --output-dir /tmp/cp-check
```

---

## Troubleshooting

**`FileNotFoundError: .lake/build/blueprint/module/<X>.json`**

`WORKSPACE_NAME` does not match your `[[lean_lib]]` name, so the lookup points at
a file Lake never wrote. Check what actually exists:

```bash
ls .lake/build/blueprint/module/
```

Whatever `<Module>.json` you see there is the name `WORKSPACE_NAME` must use
(with `.lean` appended).

**`ls .lake/build/blueprint/module/` is empty**

The build never ran, or the workspace file is not part of the library. The
workspace must be the library root: named `<Module>.lean` and matching
`[[lean_lib]] name`.

**Build output is stale after renaming a module**

`.lake/` caches per module name. After changing `<Module>`, remove the old
artifacts so Lake rebuilds rather than reusing them:

```bash
rm -f .lake/build/blueprint/module/<OldModule>.json
```

The harness does this automatically for the module it is configured to use
(`runner.py`'s `STALE_BLUEPRINT_JSON`), which is why keeping the names in sync
matters — with a mismatched name that cleanup silently does nothing.

**`repl` fails to build**

Its `rev` in `lakefile.toml` must match `lean-toolchain`.
