#!/usr/bin/env node
// ship-cycle SessionStart hook (#86).
//
// On startup / clear / compact, if the current branch has a non-terminal ship-cycle state file, print a few
// quiet facts (stage, next gate, loops, parked, state path) so a long cycle that crosses a compaction does
// not silently lose its state-file discipline. Silent in every other case.
//
// Contract, in order of importance:
//   * Never fail or stall the session: every error path ends in exit 0 with nothing on stdout, and nothing
//     is read that is not a small regular file (never a FIFO or device), UNC-style gitdir / cwd values
//     are not followed, and stdin is read only until it holds one complete JSON value.
//   * Read-only, no network, no child process: the branch comes from the HEAD file, not `git`.
//   * Nothing from the repo is free text to the model. The state file and the branch name can be written by
//     anyone with repo access, so every printed value is whitelisted: stage names and gate ids from fixed
//     vocabularies, integer counts, an ISO date, and the branch only if it matches BRANCH_RE (else it and
//     the path built from it are omitted). goal, parked.reason and gate reasons are never echoed.
//
// Working directory: the `cwd` of the hook's stdin JSON when present and usable, else process.cwd(). The
// read relies on the host closing stdin or completing the JSON value; it stops at the first complete one.
// Usage:  node session-start.cjs [--host claude|codex]
//   claude (default): JSON {hookSpecificOutput:{hookEventName,additionalContext}},
//                     state dir .claude/ship-cycle
//   codex:            plain text, state dir .codex/ship-cycle
// Opt-out: SHIP_CYCLE_HOOK=off (also 0 / false / no / disabled).
"use strict";

const fs = require("fs");
const path = require("path");
const tty = require("tty");

// Mirrors the pipeline table in skills/ship-cycle/SKILL.md (stage skill -> its gates). scripts/validate.py
// parses both and fails on any difference, so edit them together.
// stage-gates:begin
const STAGE_GATES = {
  "sc-brainstorm": ["G1"],
  "sc-design": ["G2", "G3"],
  "sc-tdd": ["G4"],
  "sc-implement": ["G5", "G6", "G7", "G7b"],
  "sc-review": ["G8"],
  "sc-qa": ["G9"],
  "sc-ship": ["G10", "G11", "G12", "G13"]
};
// stage-gates:end
// G2/G3 is one gate in the orchestrator's gate table: a value under either id (or the pair) covers both.
const ONE_GATE = { G2: ["G2/G3", "G3"], G3: ["G2/G3", "G2"] };
// Mirrors "Loop cap: 3 per gate" in skills/ship-cycle/SKILL.md (checked by scripts/validate.py).
const LOOP_CAP = 3;
const PARKED = "parked";
const RECORDED = new Set(["pass", "checklist", "degrade"]); // plus any "n/a..."
const MAX_SMALL_FILE = 4 * 1024;
const MAX_STATE_BYTES = 1024 * 1024;
const MAX_STDIN = 64 * 1024;
const STDIN_WAIT_MS = 300;
const MAX_UP = 64;
const BRANCH_RE = /^[A-Za-z0-9._/-]{1,80}$/;
const GATE_RE = /^G\d{1,2}[a-z]?$/;
const ISO_DATE_RE = /^(\d{4}-\d{2}-\d{2})(?:[T ][0-9:.]+(?:Z|[+-]\d{2}:?\d{2})?)?$/;
const OFF_VALUES = new Set(["off", "0", "false", "no", "disabled"]);
const STOP = Symbol("stop");

function isNetworkPath(p) {
  return typeof p === "string" && (p.startsWith("\\\\") || p.startsWith("//"));
}

function statOrNull(p) {
  // ENOENT / ENOTDIR: not there. Any other error (ELOOP, EACCES, ...): STOP -- do not keep probing.
  try {
    return fs.statSync(p);
  } catch (e) {
    return e && (e.code === "ENOENT" || e.code === "ENOTDIR") ? null : STOP;
  }
}

function readSmallFile(p, max) {
  const st = statOrNull(p);
  if (!st || st === STOP || !st.isFile() || st.size > max) return null;
  return fs.readFileSync(p, "utf8");
}

function stdinCwd() {
  // tty.isatty, not process.stdin: touching process.stdin makes libuv switch fd 0 to non-blocking, and a
  // read that races the host's write would then see EAGAIN and drop the cwd.
  if (tty.isatty(0)) return null;
  const chunks = [];
  let total = 0;
  let input;
  const buf = Buffer.alloc(8192);
  const pause = new Int32Array(new SharedArrayBuffer(4));
  const deadline = Date.now() + STDIN_WAIT_MS;
  for (;;) {
    let n = 0;
    try {
      n = fs.readSync(0, buf, 0, buf.length, null);
    } catch (e) {
      // A non-blocking stdin with nothing yet: wait briefly for the host's write, never spin or hang.
      if (e && e.code === "EAGAIN" && Date.now() < deadline) {
        Atomics.wait(pause, 0, 0, 5);
        continue;
      }
      break; // EOF on Windows pipes, EBADF when there is no stdin, or the EAGAIN deadline passed
    }
    if (n <= 0) break;
    total += n;
    if (total > MAX_STDIN) return null;
    chunks.push(Buffer.from(buf.subarray(0, n)));
    // Stop at the first complete JSON value: a host that writes it and keeps stdin open must not stall us.
    try {
      input = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      break;
    } catch (_) { /* incomplete so far: read on */ }
  }
  if (!total || input === undefined) return null;
  const cwd = input && typeof input === "object" ? input.cwd : null;
  if (typeof cwd !== "string" || !cwd || cwd.length > 4096 || cwd.includes("\0")) return null;
  if (!path.isAbsolute(cwd) || isNetworkPath(cwd)) return null;
  const st = statOrNull(cwd);
  return st && st !== STOP && st.isDirectory() ? cwd : null;
}

function findGitEntry(start) {
  let dir = path.resolve(start);
  for (let i = 0; i < MAX_UP; i++) {
    const candidate = path.join(dir, ".git");
    const st = statOrNull(candidate);
    if (st === STOP) return null;
    if (st) {
      if (st.isDirectory()) return { top: dir, entry: candidate, isDir: true };
      if (st.isFile() && st.size <= MAX_SMALL_FILE) return { top: dir, entry: candidate, isDir: false };
      return null; // a FIFO, device or oversized `.git`: not a repo we read
    }
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
  return null;
}

function gitDirOf(found) {
  if (found.isDir) return found.entry;
  // A worktree or submodule: `.git` is a file holding `gitdir: <path>`, relative to the file's directory.
  const text = readSmallFile(found.entry, MAX_SMALL_FILE);
  const m = text ? /^gitdir:\s*(.+?)\s*$/m.exec(text) : null;
  if (!m || isNetworkPath(m[1])) return null;
  return path.resolve(found.top, m[1]);
}

function currentBranch(gitDir) {
  const head = readSmallFile(path.join(gitDir, "HEAD"), MAX_SMALL_FILE);
  const m = head ? /^ref:\s*refs\/heads\/(.+)$/.exec(head.trim()) : null;
  return m ? m[1] : null; // detached HEAD (a bare sha) or an unexpected ref -> no branch
}

function isRecorded(value) {
  return typeof value === "string" && (RECORDED.has(value) || value.startsWith("n/a"));
}

function nextGate(stageSkill, gates) {
  // The first gate of the stage not yet recorded, or null when every one of them is.
  const record = gates && typeof gates === "object" && !Array.isArray(gates) ? gates : {};
  for (const gate of STAGE_GATES[stageSkill]) {
    const ids = [gate, ...(ONE_GATE[gate] || [])];
    if (!ids.some((id) => isRecorded(record[id]))) return gate;
  }
  return null;
}

function loopsText(loops) {
  if (!loops || typeof loops !== "object" || Array.isArray(loops)) return null;
  const parts = [];
  for (const [gate, count] of Object.entries(loops)) {
    if (!GATE_RE.test(gate)) continue;
    if (!Number.isInteger(count) || count <= 0 || count > 99) continue;
    parts.push(`${gate}=${count}/${LOOP_CAP}`);
    if (parts.length >= 13) break;
  }
  return parts.length ? parts.join(" ") : null;
}

function render(host, branch, state) {
  const stage = state.stage;
  const parked = stage === PARKED;
  let skill = stage;
  if (parked) {
    const p = state.parked;
    skill = p && typeof p === "object" ? p.resumeStage : undefined;
  }
  // Terminal (complete/failed/cancelled), unknown or missing stage -> silent.
  if (typeof skill !== "string" || !Object.prototype.hasOwnProperty.call(STAGE_GATES, skill)) {
    if (!parked) return null;
    skill = null; // parked with an unreadable resumeStage: still worth saying it is parked
  }
  const gate = skill ? nextGate(skill, state.gates) : null;
  const gateText = gate ? `next gate ${gate}` : "stage gates recorded - advance per the pipeline";
  const loops = loopsText(state.loops);
  const dir = `${host === "codex" ? ".codex" : ".claude"}/ship-cycle/`;
  const named = BRANCH_RE.test(branch);
  const on = named ? `on branch \`${branch}\`` : "(state file for the current branch)";
  let head;
  if (parked) {
    const at = state.parked && typeof state.parked.at === "string" ? ISO_DATE_RE.exec(state.parked.at) : null;
    head = `ship-cycle: parked cycle ${on}${at ? ` since ${at[1]}` : ""}`
      + (skill ? ` - resume stage ${skill}, ${gateText}` : " - resume stage unreadable");
  } else {
    head = `ship-cycle: active cycle ${on} - stage ${skill}, ${gateText}`;
  }
  const where = named
    ? `${dir}${branch.split("/").join("-")}.json`
    : `the state file beside the gate log in ${dir}`;
  const lines = [`${head}${loops ? `, loops ${loops}` : ""}.`];
  lines.push(`State: ${where}${named ? " (gate log beside it)" : ""}`
    + `${parked ? "; the park reason is recorded there" : ""}.`);
  lines.push(host === "codex"
    ? "Run the ship-cycle resume reconcile before acting."
    : "Run /ship-cycle-devkit:resume's reconcile before acting.");
  return lines.join("\n");
}

function main(argv) {
  const off = String(process.env.SHIP_CYCLE_HOOK || "").trim().toLowerCase();
  if (OFF_VALUES.has(off)) return null;
  const i = argv.indexOf("--host");
  const host = i >= 0 && argv[i + 1] === "codex" ? "codex" : "claude";

  let start = null;
  // Codex's stdin contract is unverified (docs/runtime-adapters.md), so it is not read there.
  if (host === "claude") {
    try { start = stdinCwd(); } catch (_) { start = null; }
  }
  const found = findGitEntry(start || process.cwd());
  if (!found) return null;
  const gitDir = gitDirOf(found);
  if (!gitDir) return null;
  const branch = currentBranch(gitDir);
  if (!branch) return null;
  const slug = branch.split("/").join("-"); // exactly `tr '/' '-'` (docs/state-file.md - The slug)

  const hostDir = host === "codex" ? ".codex" : ".claude";
  const statePath = path.join(found.top, hostDir, "ship-cycle", `${slug}.json`);
  const raw = readSmallFile(statePath, MAX_STATE_BYTES);
  if (raw === null) return null;
  const state = JSON.parse(raw);
  if (!state || typeof state !== "object" || Array.isArray(state)) return null;
  // Collision guard: a file whose recorded branch is another branch (lossy slug) is not this cycle's.
  if (typeof state.branch === "string" && state.branch !== branch) return null;

  const text = render(host, branch, state);
  if (!text) return null;
  if (host === "codex") return `${text}\n`;
  // ASCII-only JSON (non-ASCII as \uXXXX) so no console code page can garble it on the way in.
  const payload = { hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: text } };
  const json = JSON.stringify(payload)
    .replace(/[\u0080-\uffff]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`);
  return `${json}\n`;
}

let out = null;
try {
  out = main(process.argv.slice(2));
} catch (_) {
  out = null;
}
if (out) {
  process.stdout.on("error", () => {});
  try { process.stdout.write(out); } catch (_) { /* a closed pipe is not the session's problem */ }
}
process.exitCode = 0;
