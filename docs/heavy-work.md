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
| `heavyLock` | base path of the slot locks shared by every **one-shot** heavy command (long-lived ones go by headroom) |
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

Save the wrapper below as `heavy-run.sh` and run every one-shot heavy command through it. The wrapper
shell holds the slot on an fd and closes that fd for the job (`{fd}>&-`), so a daemon the job spawns (gradle
daemon, adb server) cannot keep the slot, the job runs exactly once, and its own exit code is returned.
Busy (`flock` exit 1) is told apart from a real `flock` error (e.g. cannot open the file) without
re-running anything. Tested with real `flock`: busy wait, N=2 slots, nesting, backgrounded children.

```bash
#!/usr/bin/env bash
# usage: LOCK=/path/base [N=1] [HEAVY_WAIT=540] [HEADROOM_MB=2048] heavy-run.sh <cmd> [args...]
# exit: the job's own code | 98 lock error, not run | 99 wait timed out, not run | 97 low headroom, not run
: "${LOCK:?heavyLock unset}"
[ -n "$SC_HEAVY_HELD" ] && exec "$@"                  # nested: outermost launcher holds the slot
n=${N:-1}; end=$((SECONDS + ${HEAVY_WAIT:-540}))
while :; do
  for k in $(seq 1 "$n"); do
    slot="$LOCK.$k"
    exec {fd}>>"$slot" || { echo "heavy: cannot open $slot" >&2; exit 98; }
    flock -n "$fd"; rc=$?
    if [ $rc -eq 0 ]; then
      # headroom check goes here, inside the lock (available MB; skip with a note if no probe)
      if [ -n "$HEADROOM_MB" ] && [ -r /proc/meminfo ]; then
        avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
        [ "$avail" -lt "$HEADROOM_MB" ] && { echo "heavy: only ${avail} MB available" >&2; exit 97; }
      fi
      SC_HEAVY_HELD="$slot" "$@" {fd}>&-               # job runs once; children do not inherit the fd
      exit $?                                          # lock released when this shell exits
    fi
    exec {fd}>&-
    [ $rc -ne 1 ] && { echo "heavy: flock error $rc on $slot" >&2; exit 98; }   # 1 = busy
  done
  [ $SECONDS -ge $end ] && { echo "heavy: lock wait timed out" >&2; exit 99; }
  sleep $((3 + RANDOM % 5))
done
```

- **Bounded wait** (`HEAVY_WAIT`, default 540 s): keep it **below the agent's tool timeout** (Claude Code
  Bash: 120 s default, 600 s max in the foreground; Codex has its own) or run the wrapper in the background
  and poll. A tool-killed or timed-out wait (exit 99) means the step is **not run** — report it like a killed
  lens, never count it as a pass, never hang a gate. Codes 97–99 are the wrapper's; the stderr `heavy:` line
  says which.
- **Nesting**: only the outermost launcher takes the lock (`SC_HEAVY_HELD`). Do not wrap overlay test
  commands that already call `flock` on the same path — that self-deadlocks.
- Headroom is checked **inside** the lock (the `HEADROOM_MB` hook; set it from `heavyHeadroomMB`).

## Long-lived heavy jobs (emulator, dev server, daemons)

Never run these in the foreground under `flock`; they would hold a slot for the whole session. Decision: they
are **governed by the headroom check, not by the lock**. Take a slot only to launch (check headroom, start
the process detached, release), record its PID, and stop it at teardown — only jobs this session started:

```bash
flock -n -o "$LOCK.1" sh -c 'nohup <cmd> >job.log 2>&1 & echo $! >job.pid'
```

The launching shell exits at once, so the slot frees; the job's PID is tracked in `job.pid`. A foreground
run, or `flock -o "$LOCK.1" <cmd> &`, holds the slot for the job's whole life — do not. Never start a build while an emulator runs if headroom is short: stop the emulator first.

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
the lock is lost and `heavyHeadroomMB` with it: run heavy work sequentially, one at a time, and print that.
Otherwise nothing changes.
