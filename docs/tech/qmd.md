# qmd — local search over markdown (tobi/qmd), looked up 2026-09-24

## Installed here 2026-09-24 (measured)
- Node 24.19.0 LTS via `winget install --id OpenJS.NodeJS.LTS --exact`
  (admin prompt). npm 11.17.0.
- `npm install -g @tobilu/qmd` -> qmd 2.8.3. **Trap:** npm 11 blocks
  install scripts by default and says so in a warning: node-llama-cpp
  postinstall and 5 tree-sitter builds did not run. AST chunking still
  reports "active" (it uses .wasm grammars).
- Plugin: `claude plugin marketplace add tobi/qmd`, `claude plugin install
  qmd@qmd` (user scope). It carries 2 skills and the MCP server
  `qmd mcp`. `claude mcp list` -> `plugin:qmd:qmd ... Connected`.
- **Trap:** a shell or app started before Node was installed has no `qmd`
  on PATH. Restart the desktop app once.
- Config: `C:\Users\jacek\.config\qmd\index.yml`. Index:
  `C:\Users\jacek\.cache\qmd\index.sqlite`.
- **Trap:** `docs/tech/qmd-bench.md` holds the test questions word for
  word; it came up first until excluded with `ignore:` under the
  collection in index.yml.
- Built in: `qmd bench <fixture.json>` runs a search-quality benchmark.

## Speed on this laptop, docs/ only (35 files, 93 chunks), 2026-09-24
Question: "Background hiss grows towards the end of the film. What fixed it?"
(answer: 0003). CLI, each call loads its models afresh.
| Call | Seconds | Result |
|---|---|---|
| `qmd embed` (incl. 318 MB download) | 120.6 | 93 chunks |
| `qmd search` (keywords, no model) | 0.5 | |
| `qmd query`, 1st (incl. 1.8 GB download) | 146.1 | **crashed** loading the reranker |
| `qmd query`, 2nd | 141.7 | 2 results, 0011 then a plan: **wrong** |
| `qmd vsearch` | 15.2 | 0003 2nd (tied 0.48 with a plan), audio.md 3rd: right |
- The query expander rewrote the hiss question as "Importance of setting
  the right tone": the 1.7B model gets this vocabulary wrong.
- Not yet known: why the reranker crashed once, and whether forcing CPU
  (not the Intel iGPU, issue #969) changes the 140 s.

## Code collection, added 2026-09-24 (measured)
- `qmd collection add . --name code --mask "ffilm/**/*.py,tests/**/*.py"`,
  then `qmd context add qmd://code "..."`, then
  `qmd embed --chunk-strategy auto`.
- 90 files indexed (`ffilm/__init__.py` is empty, so left out). Embedded
  **580 chunks in 9 m 15 s** from the shell, no error.
- The running MCP server searched it at once, no restart: bench Q8
  (booth.py, rank 1, 1.29 s) and Q9 (scaffold.py, rank 5, 1.36 s;
  guide.py first). Pass `collections: ["code"]`.
- **The index does not follow the code.** After code changes run
  `qmd update`, then `qmd embed --chunk-strategy auto` (only changed
  files are re-embedded; not yet timed).
- Files are read as they are on disk (CRLF), so snippets end in `\r`.

## History collection, added 2026-09-24 (measured)
- qmd never calls git, so the log is written to files first: one file per
  commit in `C:\Users\jacek\.cache\qmd\history\` (outside the repo),
  `<date>-<hash>.md` = `# <hash> <date> <subject>`, blank line, message.
  191 files, 193 chunks embedded in 1 m 30 s.
  `qmd collection add <that folder> --name history`, `qmd context add`,
  `qmd embed`. Pass `collections: ["history"]`.
- **One file for the whole log did not work:** qmd returns one hit per
  file, so every search returned 1 result, and not the right commit (the
  music question gave d2c51b5, not 878207e). One file per commit fixed it.
- Bench Q10 now: 878207e first, 1.54 s. "Which commit fixed the microphone
  starting later than the camera?": 2881ea5 first, c802fcd (the fix)
  second, 1.31 s.
- **Refresh after new commits** (only the new ones are re-embedded; not
  yet timed): write a file for each new hash the same way, e.g.
  `git log -1 --format='# %h %ad %s%n%n%b' --date=short <hash> >
  <folder>/<date>-<hash>.md`, then `qmd update` and `qmd embed`.
- `qmd cleanup` removed 3 orphaned records after the switch.

## Trap: installed inside the Claude app's private folder (measured 2026-09-25)
- The Claude desktop app is a Windows Store (MSIX) package
  (`Claude_pzs8sxrjxfjjc`). Anything it writes to `AppData\Roaming`,
  including `npm install -g` run from a Claude session, lands in
  `C:\Users\jacek\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\npm\`.
  Inside the app it looks like `AppData\Roaming\npm`. Every other program
  (Obsidian/Claudian, a normal terminal) sees no npm folder at all:
  Claudian, same user and host, got `Test-Path ...\Roaming\npm\qmd.cmd` = False.
- Not affected: Node itself (`C:\Program Files\nodejs`), the index and
  models (`~\.cache\qmd`), the config (`~\.config\qmd`), `~\.claude`.
- So global npm tools for use outside the app must be installed outside
  `AppData`, or from a normal terminal.
- **Fixed 2026-09-25** by moving the folder with the apps closed: a .bat
  run from Explorer did `move <LocalCache>\Roaming\npm %APPDATA%\npm`
  (same drive, so a rename). Measured afterwards from inside the Claude
  app: the private copy is gone, `qmd --version` = 2.8.3 from
  `C:\Users\jacek\AppData\Roaming\npm`, `claude mcp list` =
  `plugin:qmd:qmd ... Connected`. Index, models and config untouched.
  The app finds the real folder once its private copy is gone.

## From Obsidian (Claudian), looked up 2026-09-25, not tried
- Claudian's README (YishenTu/claudian) says only: MCP servers come from
  "each coding agent's native CLI-managed MCP configuration". It does not
  say whether plugin-provided servers (our `qmd@qmd`) are loaded, which
  transports it supports, or anything about Windows.
- 2026-09-25: this Claude session started with qmd "failed to connect",
  while `claude mcp list` from the shell said Connected minutes later.
  Cause not measured. Happened again 2026-09-25 after the move: the
  failure is cached for 15 min and the session cannot force a retry.

Below: from the README and the issue list.

## What it is
A command-line search engine over folders of markdown: keyword (BM25),
vector, and a hybrid with re-ranking. Everything runs locally. It also runs
as an MCP server, so Claude can call it as a tool.

## Install
- Needs Node >= 22 or Bun >= 1.0. On 2026-09-24 this machine had neither
  (`node`, `npm`, `bun` not on PATH).
- `npm install -g @tobilu/qmd` (or `bun install -g @tobilu/qmd`)
- Claude Code plugin (starts the MCP server for Claude):
  `claude plugin marketplace add tobi/qmd`, then `claude plugin install qmd@qmd`
- Or by hand: MCP server `{"command": "qmd", "args": ["mcp"]}`

## Where it puts things (outside the repo)
- Models, downloaded on first use, about 2 GB in total, to `~/.cache/qmd/models/`:
  embeddinggemma-300M (~300 MB), qwen3-reranker-0.6b (~640 MB),
  qmd-query-expansion-1.7B (~1.1 GB)
- Index: `~/.cache/qmd/index.sqlite`. Config: `~/.config/qmd/index.yml`

## Use
```
qmd collection add <folder> --name <name>
qmd context add qmd://<name> "what is in it"
qmd embed                      # builds the vectors
qmd search "words"             # keyword only, no models
qmd vsearch "meaning"          # vectors only
qmd query "question"           # hybrid + re-rank, uses all 3 models
```

## Masks, code, refresh, MCP tools (README + src/ast.ts, 2026-09-24)
- Any text type via a mask: `qmd collection add <dir> --name x --mask "**/*.py,**/*.md"`
  (comma = union).
- Code: `qmd embed --chunk-strategy auto` splits .py (also ts/js/go/rs) at
  function/class boundaries with tree-sitter; falls back to regex if the
  grammar fails to load. Other text: ~900-token chunks, 15% overlap, cut at
  headings first.
- `qmd update` re-scans all collections (runs a collection's `update`
  command first, if one is set). New text needs `qmd embed` after it.
- MCP server tools: `query` (hybrid lex/vec/hyde + rerank), `get` (path or
  #docid, line range), `multi_get` (glob), `status`.

## Git: not used (read in src/store.ts, 2026-09-24)
- No git calls at all. `.git` is on a fixed skip list (with node_modules,
  .cache, vendor, dist, build).
- It indexes the files on disk as they are now: tracked, untracked and
  uncommitted alike. It does not read .gitignore.
- Change detection is a hash of the content. A changed file replaces its old
  version in the index, so the index keeps no history.
- It only reads the folder. The index lives in ~/.cache, not in the repo.
- Default mask `**/*.md`: `.txt` (scripts, narration) is NOT indexed unless
  the mask is changed. Dot-folders (`dot: false`) are skipped, so
  `.claude/` (skills) is not indexed either.

## Traps on Windows (from the issue list, 2026-09-24)
- #981 Windows path support: open, still being worked on.
- #968 the `embed` lock does nothing on Windows (closed). #924 same area, open.
- #969 Vulkan picks the Intel integrated GPU. This laptop has Intel UHD 630
  plus a Radeon 540X, so this one applies.
- #977 `vsearch`/`query` hang with no error if a model file is missing or
  corrupt. A half-finished download looks like a freeze.
- #935 `embed` fails partway with DisposedError (2.8.3), open.
