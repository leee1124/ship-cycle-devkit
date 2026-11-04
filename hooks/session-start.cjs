#!/usr/bin/env node
// ship-cycle SessionStart hook (#86).
//
// On startup / clear / compact, if the current branch has a non-terminal ship-cycle state file, print a few
// quiet facts (stage, next gate, loops, parked, state path) so a long cycle that crosses a compaction does
// not silently lose its state-file discipline. Silent in every other case.
//
// Contract, in order of importance:
//   * Never fail the session: every error path ends in exit 0 with nothing on stdout.
//   * Read-only, no network, no child process: the branch comes from the HEAD file, not `git`.
//   * The state file is data written by anyone with repo access: only whitelisted fields are printed, each
//     validated against a fixed shape or vocabulary; free text (goal, parked.reason) is never echoed.
//
// Usage:  node session-start.cjs [--host claude|codex]
//   claude (default): JSON {hookSpecificOutput:{hookEventName,additionalContext}} on stdout, state dir .claude/ship-cycle
//   codex:            plain text on stdout, state dir .codex/ship-cycle
// Opt-out: SHIP_CYCLE_HOOK=off (also 0 / false / no / disabled).
"use strict";

const fs = require("fs");
const path = require("path");

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
// Mirrors "Loop cap: 3 per gate" in skills/ship-cycle/SKILL.md (checked by scripts/validate.py).
const LOOP_CAP = 3;
const PARKED = "parked";
const MAX_FIELD = 100;
const MAX_STATE_BYTES = 1024 * 1024;
const MAX_UP = 64;
const GATE_RE = /^G\d{1,2}[a-z]?$/;
const ISO_DATE_RE = /^(\d{4}-\d{2}-\d{2})(?:[T ][0-9:.]+(?:Z|[+-]\d{2}:?\d{2})?)?$/;
const CONTROL_RE = new RegExp("[\\u0000-\\u001f\\u007f-\\u009f\\u200b-\\u200f\\u2028-\\u202e\\u2060-\\u206f\\ufeff]", "g");
const OFF_VALUES = new Set(["off", "0", "false", "no", "disabled"]);

function clean(value) {
  // Strip control / format / line-separator characters and cap the length: a branch name or a vocabulary
  // value is the only thing that reaches this, but the cap holds even if that changes.
  return String(value).replace(CONTROL_RE, "").slice(0, MAX_FIELD);
}

function findGitEntry(start) {
  let dir = path.resolve(start);
  for (let i = 0; i < MAX_UP; i++) {
    const candidate = path.join(dir, ".git");
    let st = null;
    try { st = fs.statSync(candidate); } catch (_) { st = null; }
    if (st) return { top: dir, entry: candidate, isDir: st.isDirectory() };
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
  return null;
}

function gitDirOf(found) {
  if (found.isDir) return found.entry;
  // A worktree or submodule: `.git` is a file holding `gitdir: <path>`, relative to the file's directory.
  const text = fs.readFileSync(found.entry, "utf8");
  const m = /^gitdir:\s*(.+?)\s*$/m.exec(text);
  if (!m) return null;
  return path.resolve(found.top, m[1]);
}

function currentBranch(gitDir) {
  const head = fs.readFileSync(path.join(gitDir, "HEAD"), "utf8").trim();
  const m = /^ref:\s*refs\/heads\/(.+)$/.exec(head);
  return m ? m[1] : null; // detached HEAD (a bare sha) or an unexpected ref -> no branch
}

function isDone(value) {
  return typeof value === "string" && (value === "pass" || value.startsWith("n/a"));
}

function nextGate(stageSkill, gates) {
  const list = STAGE_GATES[stageSkill];
  const record = gates && typeof gates === "object" && !Array.isArray(gates) ? gates : {};
  const combined = list.join("/");
  if (isDone(record[combined])) return list[list.length - 1];
  for (const gate of list) {
    if (!isDone(record[gate])) return gate;
  }
  return list[list.length - 1];
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

function render(host, branch, slug, state) {
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
  const loops = loopsText(state.loops);
  const where = `${host === "codex" ? ".codex" : ".claude"}/ship-cycle/${clean(slug)}.json`;
  const b = clean(branch);
  let head;
  if (parked) {
    const at = state.parked && typeof state.parked.at === "string" ? ISO_DATE_RE.exec(state.parked.at) : null;
    head = `ship-cycle: parked cycle on ${b}${at ? ` since ${at[1]}` : ""}`
      + (skill ? ` - resume stage ${skill}, next gate ${gate}` : " - resume stage unreadable");
  } else {
    head = `ship-cycle: active cycle on ${b} - stage ${skill}, next gate ${gate}`;
  }
  const lines = [`${head}${loops ? `, loops ${loops}` : ""}.`];
  lines.push(`State: ${where} (gate log beside it)${parked ? "; the park reason is recorded there" : ""}.`);
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

  const found = findGitEntry(process.cwd());
  if (!found) return null;
  const gitDir = gitDirOf(found);
  if (!gitDir) return null;
  const branch = currentBranch(gitDir);
  if (!branch) return null;
  const slug = branch.split("/").join("-"); // exactly `tr '/' '-'` (docs/state-file.md — The slug)

  const statePath = path.join(found.top, host === "codex" ? ".codex" : ".claude", "ship-cycle", `${slug}.json`);
  const st = fs.statSync(statePath);
  if (!st.isFile() || st.size > MAX_STATE_BYTES) return null;
  const state = JSON.parse(fs.readFileSync(statePath, "utf8"));
  if (!state || typeof state !== "object" || Array.isArray(state)) return null;
  // Collision guard: a file whose recorded branch is another branch (lossy slug) is not this cycle's.
  if (typeof state.branch === "string" && state.branch !== branch) return null;

  const text = render(host, branch, slug, state);
  if (!text) return null;
  if (host === "codex") return `${text}\n`;
  // ASCII-only JSON (non-ASCII as \uXXXX) so no console code page can garble it on the way in.
  const json = JSON.stringify({ hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: text } })
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
