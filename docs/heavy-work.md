# Heavy work — serializing resource-hungry jobs on a small host

Several things can run at once and exhaust memory: a test suite with many workers, a release build, an
emulator, a dev server, a browser, a CI runner on the same box. This file is the single home of the rule;
the orchestrator, sc-implement, sc-review and sc-qa point here instead of giving ad-hoc advice.

## What is heavy

Heavy = a *job*, not an agent: test runners with many workers (full suites), compilers/bundlers (gradle,
`tsc` on a big repo), release builds, emulators/simulators, dev servers, browsers, and any self-hosted CI
runner on the same machine. A read-only reviewer or research agent costs no RAM beyond the CLI and is **not**
heavy; the heavy part is what it launches (a lens that runs the suite, a QA agent that boots an emulator).
Cheap, targeted runs (one test file, a lint) are not heavy.

## Settings (overlay `env`, all optional)

| key | meaning |
|---|---|
| `heavyLock` | path of a lock file shared by **every** heavy command, across sessions and worktrees |
| `maxConcurrentHeavy` | integer ≥ 1: how many heavy jobs may run at once; default 1 when `heavyLock` is set |
| `heavyHeadroomMB` | integer: refuse to launch a heavy job below this much free memory; default off |

**Unset = today's behaviour** (no serialization; only advice to be careful). Semantics, kept simple:

- `heavyLock` set → every heavy command runs under it. One slot: `flock <heavyLock> <cmd>`.
- `maxConcurrentHeavy` N > 1 with `heavyLock` → N slots `<heavyLock>.1` … `<heavyLock>.N`; take the first
  free (`flock -n`), else wait. A counting semaphore is built from N plain locks so no extra tool is needed.
- `maxConcurrentHeavy` without `heavyLock` → caps what *this* orchestrator starts at once (queue in-session);
  it cannot see other sessions. Prefer setting `heavyLock` when more than one session shares the host.
- `heavyHeadroomMB` → before each launch read free memory (`free -m`; on WSL also the Windows host, where an
  emulator lives); below the threshold, wait or stop a running heavy job first — never start a build while an
  emulator runs if headroom is short. Keep ≥ ~2 GB free.

## Rules for the orchestrator

1. **Tag** heavy work when planning each stage (full suite, release build, device/emulator QA) and queue it
   under the lock; log "heavy: queued/started/finished" lines so waits are visible, not silent hangs.
2. **Pass the rule into every agent prompt that may run heavy work** — subagents do not inherit it. Give the
   lock path, the slot count, and the worker caps below, verbatim.
3. **Cap workers per runner** even under the lock (e.g. `jest --maxWorkers=2`, `--workerIdleMemoryLimit`;
   gradle `--max-workers`), since one job can exhaust memory alone.
4. **Check a same-box CI runner is idle** before a heavy job.
5. **Killed for memory?** Run the rest sequentially and do not auto-relaunch (see sc-review).
6. **Kill runaway jobs by PID**, never by process name (a pattern can match the matcher or a sibling session).

## No `flock` (Windows, minimal images)

Portable lock: `mkdir <heavyLock>.d` succeeds for exactly one caller; run the job; `rmdir` it afterwards
(also on failure). Write the PID inside; a lock whose PID is gone may be reported to the user, never
silently stolen. With no lock primitive at all, the setting degrades to **one heavy job at a time, run
sequentially** by the orchestrator — say so once at PREFLIGHT.

## When `env` is ignored

A schema-invalid `env` block is ignored (SC-DEGRADE-ENV) — which loses the lock. Do not run unserialized:
fall back to **sequential heavy work, one at a time**, and print that the lock is not in force.
