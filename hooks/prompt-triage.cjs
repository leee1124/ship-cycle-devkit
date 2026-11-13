#!/usr/bin/env node
// ship-cycle UserPromptSubmit hook — entry triage (#107). Opt-in: silent unless SHIP_CYCLE_AUTOSTART is on.
//
// When enabled, adds one fixed instruction to each prompt: classify the request before acting (code change
// that ships as a PR / design-only / question, research or writing) and say the decision in one line the
// user can override. It decides nothing itself.
//
// Contract:
//   * Never fail or stall the session: every path exits 0 (exitCode, no process.exit); stdin (the prompt) is never read, so a
//     huge or never-closed stdin cannot stall it.
//   * Nothing from the prompt, the repo or the environment is echoed: the output is a fixed ASCII string.
//   * No file reads, no network, no child process.
// Cost: registered for every plugin user, so node starts on each prompt even when disabled (~50-100 ms).
// Usage:  node prompt-triage.cjs [--host claude|codex]
//   claude (default): JSON {hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext}}
//   codex:            plain text
// Opt-in: SHIP_CYCLE_AUTOSTART=on (also 1 / true / yes / enabled). Anything else, or unset: silent.
"use strict";

const ON_VALUES = new Set(["on", "1", "true", "yes", "enabled"]);

// triage-text:begin
const TRIAGE_TEXT =
  "ship-cycle entry triage (SHIP_CYCLE_AUTOSTART): if a ship-cycle is already active on this branch, or this " +
  "message answers a question you asked, continue without a new triage line. Otherwise, before acting, " +
  "classify the request - " +
  "(a) a code change that ships as a PR -> start a cycle with the ship-cycle-devkit:ship-cycle skill (PREFLIGHT); " +
  "(b) work that ends in a design document -> start a cycle and propose the design-only route at G1; " +
  "(c) one stage's job (review this branch, critique a design, parity audit) -> run that skill standalone; " +
  "(d) a question, research or writing task -> no cycle. " +
  "State the result first, in one line the user can override: " +
  "'triage: <code change|design-only|one stage|question/research/writing> -> <cycle|standalone <skill>|no cycle> - <reason>'. " +
  "Never skip the cycle silently for a code change.";
// triage-text:end

function main() {
  let out = null;
  try {
    const flag = String(process.env.SHIP_CYCLE_AUTOSTART || "").trim().toLowerCase();
    if (ON_VALUES.has(flag)) {
      const i = process.argv.indexOf("--host");
      const host = i >= 0 ? process.argv[i + 1] : "claude";
      out = host === "codex"
        ? TRIAGE_TEXT + "\n"
        : JSON.stringify({ hookSpecificOutput: { hookEventName: "UserPromptSubmit", additionalContext: TRIAGE_TEXT } }) + "\n";
    }
  } catch (_) {
    out = null;
  }
  process.exitCode = 0;
  process.stdout.on("error", () => {}); // a closed pipe must not turn into a failure
  if (out) {
    try { process.stdout.write(out); } catch (_) { /* nothing to do */ }
  }
  // No explicit exit call: it can cut off an asynchronous stdout pipe before the write drains.
}

main();
