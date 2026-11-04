# Heavy work — serializing resource-hungry jobs on a small host

Several things can run at once and exhaust memory: a test suite with many workers, a release build, an
emulator, a dev server, a browser, a CI runner on the same box. This file is the single home of the rule;
the orchestrator, sc-implement, sc-review and sc-qa point here instead of giving ad-hoc advice.

## What is heavy

Heavy = a *job*: test runners with many workers (full suites), compilers/bundlers (gradle, `tsc` on a big
repo), release builds, emulators/simulators, dev servers, browsers, a self-hosted CI runner on the same box.
A read-only reviewer or research agent adds little beyond its own CLI process (host-dependent: separate
CLI/Codex subagent processes still cost memory, so many at once can matter) and is not itself heavy; the
heavy part is what it launches. Cheap targeted runs (one test file, a lint) are not heavy.

## Settings (overlay `env`, all optional)

| key | meaning |
|---|---|
| `heavyLock` | base path of the lock files shared by **every** heavy command, across sessions and worktrees |
| `maxConcurrentHeavy` | integer >= 1: heavy jobs allowed at once (N slots); effective value 1 if unset |
| `heavyHeadroomMB` | integer: free memory required before launching a heavy job; default off |

**All unset = today's behaviour** (no serialization). Without `heavyLock` on a small host, run
heavy-launching lenses/agents sequentially. Semantics:

- **Always slot files** `<heavyLock>.1` … `<heavyLock>.N` (N = `maxConcurrentHeavy`, N = 1 gives `.1`), so
  sessions configured with different N still exclude each other on slot 1.
- `maxConcurrentHeavy` without `heavyLock` caps what this orchestrator starts in-session only; it cannot see
  other sessions. Set `heavyLock` when several sessions share the host.
- `heavyHeadroomMB` works with or without `heavyLock`: without a lock it is a pre-launch check only.

## Running a one-shot heavy job (suite, build)

Take the first free slot, waiting a bounded time; run with `-o` so the lock fd is not inherited by children
(a daemon the job spawns — gradle daemon, adb server — would otherwise hold the slot forever):

```bash
# SC_HEAVY_HELD is set by the outermost launcher; inner wrappers see it and run the command directly.
[ -n "$SC_HEAVY_HELD" ] && exec "$@"
end=$((SECONDS+${HEAVY_WAIT:-900})); n=${N:-1}
while [ $SECONDS -lt $end ]; do
  for k in $(seq 1 "$n"); do
    SC_HEAVY_HELD="$LOCK.$k" flock -n -E 99 -o "$LOCK.$k" "$@"; rc=$?
    [ $rc -ne 99 ] && exit $rc   # 99 = slot busy; any other code is the job's own
  done
  sleep $((3 + RANDOM % 5))
done
echo "heavy: lock wait timed out" >&2; exit 99
```

(`-E 99` makes "busy" distinct from the job's own exit status; a job that itself exits 99 is ambiguous —
pick another code then.)

- **Bounded wait** (default 15 min): on timeout the step is **not run** — report it like a killed lens, never
  count it as a pass, never hang a gate.
- **Nesting**: only the outermost launcher takes the lock (`SC_HEAVY_HELD`). Do not wrap overlay test
  commands that already call `flock` on the same path — that self-deadlocks.
- Check headroom **inside** the lock, immediately before the job starts.

## Long-lived heavy jobs (emulator, dev server, daemons)

Never run these in the foreground under `flock`; they would hold a slot for the whole session. Decision: they
are **governed by the headroom check, not by the lock**. Take a slot only to launch (check headroom, start
the process detached with `flock -o`, release), record its PID, and stop it at teardown — only jobs this
session started. Never start a build while an emulator runs if headroom is short: stop the emulator first.

## Headroom (`heavyHeadroomMB`)

Read the *available* figure, not free: Linux `free -m` (`available` column); macOS `vm_stat` /
`memory_pressure`; Windows `Get-CimInstance Win32_OperatingSystem` (`FreePhysicalMemory`, KB); on WSL also the
Windows host via `powershell.exe`, where an emulator lives. Keep >= ~2 GB. Below the threshold: wait
(bounded) or stop a heavy job **this session started**. No probe available: skip the check, advisory, and say
so once.

## Rules for the orchestrator

1. **Tag** heavy work when planning each stage (full suite, release build, device/emulator QA) and queue it;
   log "heavy: queued/started/finished" so waits are visible.
2. **Pass the rule into every agent prompt that may run heavy work** — subagents do not inherit it. Give the
   lock path, slot count and wait bound verbatim, and the worker caps the overlay's test commands specify
   (e.g. `jest --maxWorkers=2`, `--workerIdleMemoryLimit`, gradle `--max-workers`).
3. **Check a same-box CI runner is idle** before a heavy job.
4. **Killed for memory?** Run the rest sequentially, do not auto-relaunch (see sc-review).
5. **Kill runaway jobs by PID**, never by process name.

## No `flock` (Windows, minimal images)

Portable test-and-set: `mkdir <heavyLock>.<k>.d` succeeds for exactly one caller (PowerShell:
`New-Item -ItemType Directory -ErrorAction Stop`; or `cmd /c mkdir`). Write `pid`, start time and hostname
into `<dir>/pid` after creating it; a dir with no `pid` yet counts as **held**. Cleanup: `rm <dir>/pid &&
rmdir <dir>`, also on failure. SIGKILL/OOM leaves stale locks: wait the bounded time, then report the lock
(path, recorded PID) and stop or ask the user — never steal silently. With no lock primitive at all the
setting degrades to **one heavy job at a time, sequential**; say so once at PREFLIGHT. Put the lock path
inside the workspace or `$TMPDIR` when the sandbox forbids `/tmp`.

## When `env` is ignored

A schema-invalid `env` is ignored (SC-DEGRADE-ENV). If the raw `env` had `heavyLock` or `maxConcurrentHeavy`,
the lock is lost: run heavy work sequentially, one at a time, and print that. Otherwise nothing changes.
