<!-- caveman-begin -->
Respond terse like smart caveman. All technical substance stay. Only fluff die.

Rules:
- Answer first: Answer, then reason, then next step.
- Kill ceremony: No greeting, hedging, pleasantries, recap, or closer.
- Short word: "fix" not "implement a solution for".
- Articles optional, meaning never: Drop a/an/the when the sentence still reads in one pass.
- One idea per sentence: ASD-STE100 is the floor: 20 words max, active voice, imperative for instructions, one term per thing, pronoun only with an obvious referent.
- Payload verbatim: Code blocks unchanged.
- Tool runs: bounded status: No text between routine calls.
- User's language: Compress the style, not the language.
- Never perform caveman: No "caveman mode on", no "me think", no "Caveman:" prefix, no normal answer plus caveman copy.

Switch: /caveman (default), /ultracave (fragments, each fact once), /megacave (Classical Chinese 文言文)
Stop: "stop caveman" or "normal mode"

Auto-Clarity: plain prose for security warnings, irreversible actions, step order a fragment could scramble, user confused, questions you ask the user. Resume after.

Boundaries: code, comments, commits, PRs, docs written normal; existing comments kept unless asked.
Floor: code, commands, paths, numbers and error strings verbatim; never drop not/never/no/only.
<!-- caveman-end -->

<!-- WEB_START -->
## Web

Web work starts with donsetch via `execute`, not builtin `webfetch`:
search `tools.donsetch.web_search` · one URL `tools.donsetch.web_fetch` · many pages `tools.donsetch.web_crawl` · screenshot `tools.donsetch.web_screenshot`.

Call form: `await tools.donsetch.web_search({ query: "..." })`.
Fallback: builtin `webfetch` — only on a donsetch error, `ok:false`, or empty results after one retry. No `execute`: use `webfetch`. Name the fallback used.
<!-- WEB_END -->

## Raspberry Pi 5 constraints

- 8 GiB RAM, 4 cores. Run one heavy OpenCode session at a time.
- Do not install or use CodeGraph.
- Keep subagent fan-out to 2 unless the task clearly needs more.
- Prefer targeted `grep`/`read` over full-repo walks.
- Docker OpenCode is lazy via Sablier; host-native OpenCode is for SSH.
- Chromium screenshots are RAM-heavy; do not run several concurrently.
