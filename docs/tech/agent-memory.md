# Agent memory and search — what was looked up, 2026-09-24

Asked after the clipped-last-word fault (docs/OPEN.md): would a vector
database help Claude remember and not break what works?

## Semantic code search (vector index behind an MCP server)
- Exists: zilliztech/claude-context (BM25 + vectors, Milvus), vectorgrep
  (LanceDB, local), Code-Index-MCP. Claimed gain: fewer tokens spent
  finding code (~40% over a session, vendor's own benchmark).
- Helps FINDING in a big codebase. It does not check what a change breaks.
  Here the repo is tens of files and the fault was never a search miss.

## Regressions — the one study that measured it
TDAD, arXiv 2603.17973 (SWE-bench Verified, open models, 100 and 25 tasks):
- A **map from source code to the tests that cover it**, given to the
  agent as a plain text file: regressions 6.08% -> 1.82%.
- **Telling the agent to do TDD, without that map: regressions 9.94%,
  worse than doing nothing.** "Information beats instructions."
- Caveat: other models, small samples. Not measured on this repo.

## What this means here
- More rules in a skill are not the fix. A checklist step like "who else
  uses this?" is the kind of instruction the study found useless.
- The fix is information: which function feeds which (code-map.md) and
  which test guards which rule, kept next to the code, plus a check on
  the film itself (`film check`) that measures the result.
