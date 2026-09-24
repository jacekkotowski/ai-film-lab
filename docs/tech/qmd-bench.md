# qmd bench — 10 questions, grep vs qmd

Written 2026-09-24, BEFORE qmd was installed, so the questions could not
be picked to suit it. Each question is phrased the way a note or a new
session would ask it. The answer was checked by reading the file. The grep
terms were fixed before running, taken from the question's own words.

## Rules
- **Search scope, same for both:** `docs/**/*.md`, the three `CLAUDE.md`,
  `HOW_TO_USE.md`, `ffilm/**/*.py`, `tests/**/*.py`, `.claude/skills/**/*.md`.
  History questions search commit messages (`git log --grep` / the
  `history` collection).
- **grep:** `git grep -i -l -E "<terms>"`, case-insensitive, files only.
- **qmd:** `qmd query "<question>"`, the top 5 results.
- **Found** = an accepted file is in the result. **Useful** = found AND at
  most 5 files to read (one screen).

## Questions
| # | Question | Accepted answer | grep terms |
|---|---|---|---|
| 1 | A photo whose file name has Polish letters comes out blank. Why? | `docs/tech/opencv.md`, `ffilm/pix.py` | `Polish letters\|blank` |
| 2 | Background hiss grows towards the end of the film. What fixed it? | `docs/decisions/0003-gate-before-the-expander.md` | `hiss` |
| 3 | Why does my narration play faster than I spoke it? | `docs/decisions/0010-your-narration-is-you-talking.md`, `ffilm/record.py` | `faster than` |
| 4 | My voice is heard before my lips move. By how much, and why? | `docs/tech/sync.md` | `before.*lips\|lips move` |
| 5 | Why is the lock file committed to the repository? | `docs/decisions/0001-lock-the-dependencies.md` | `lock file` |
| 6 | A take plays back as a frozen picture. What is wrong? | `docs/decisions/0004-recording-faults-are-usually-the-device.md`, `docs/tech/recording.md` | `frozen` |
| 7 | How loud is the background music set, and why that number? | `docs/decisions/0007-music-level-and-repeats.md`, `ffilm/audio.py` | `music.*loud\|loud.*music` |
| 8 | Where does the program decide which text the recording window opens? | `ffilm/booth.py` (`script_path`), `docs/tech/code-map.md` | `recording window` |
| 9 | Which code puts the camera intro at the start of the film and the closing at the end? | `ffilm/scaffold.py` (`place_takes`), `docs/tech/code-map.md` | `intro.*closing` |
| 10 | When did the music stop cutting out at the last word, and in which commit? | commit `878207e` | `git log -i --grep "music"` |

## Results
(filled in below, one table per run)

### grep, 2026-09-24 (commit d2c51b5; script: git grep as in Rules)
| # | files returned | found | useful | ms | why it missed |
|---|---|---|---|---|---|
| 1 | 14 | no | no | 98 | opencv.md says "non-ASCII letters", "returns None" |
| 2 | 6 | no | no | 74 | 0003 says "noise", never "hiss" |
| 3 | 0 | no | no | 72 | 0010 says "speed", "1.2" |
| 4 | 2 | yes | **yes** | 80 | |
| 5 | 1 | yes | **yes** | 79 | |
| 6 | 9 | yes | no | 73 | |
| 7 | 7 | yes | no | 81 | |
| 8 | 15 | no | no | 71 | booth.py says "script", "text" |
| 9 | 22 | yes | no | 74 | |
| 10 | 17 commits | yes (3rd) | no | 101 | |

**grep: found 6/10, useful 2/10, 71–101 ms each.** Every miss is the same
kind: the question uses a different word than the file.

### qmd through the MCP `query` tool, 2026-09-24 (commit b3e7915)
Not the Rules' `qmd query "<question>"`: the searches were typed, as
CLAUDE.md prescribes. Per question: `vec` = the question word for word,
`lex` = keywords taken from the question only, `collections: docs`,
`limit: 5`. Whether the reranker ran is not known. ms = wall clock of the
call from two `date` calls (includes tool overhead); Q2 and Q5 were
retries, not timed; Q1's is an upper bound (includes a turn gap).

| # | rank of accepted file | found | useful | ms | note |
|---|---|---|---|---|---|
| 1 | 1 (opencv.md) | yes | **yes** | <=2650 | |
| 2 | 2 (0003) | yes | **yes** | — | top hit was an unrelated plan |
| 3 | 4 (0010) | yes | **yes** | 1050 | top hit was a plan quoting "faster" |
| 4 | 2 (sync.md) | yes | **yes** | 1390 | 0011 first |
| 5 | 1 (0001) | yes | **yes** | — | |
| 6 | 1 (recording.md), 0004 3rd | yes | **yes** | 1000 | |
| 7 | none | **no** | no | 1350 | 0007 not in the 5; audio.py is not indexed |
| 8 | 1 (code-map.md) | yes | **yes** | 1190 | booth.py is not indexed |
| 9 | 4 (code-map.md) | yes | **yes** | 1630 | scaffold.py is not indexed |
| 10 | 2 (OPEN.md holds `878207e`) | yes | **yes** | 1160 | no `history` collection; the hash is in OPEN.md |

**qmd (MCP, typed searches): found 9/10, useful 9/10 (every result list
had 5 files), 1.0–1.6 s per warm call.** Rank 1 in only 4 of 10. Q10
counts as found because the answer is in the snippet; that is a judgement.

Failures while running it: "interrupted" on 5 calls (likely a user
message arriving mid-call; not confirmed) and `Object is disposed` on 6
calls in a row right after Q4; the same calls worked when retried. Cause
of the second not measured.

Second full run, same searches, nothing else running (23:00:54–23:01:09):
**10/10 returned, no errors, 14.8 s in total, 1.24–1.65 s per call**
(Q1 1.47, Q2 1.54, Q3 1.47, Q4 1.50, Q5 1.54, Q6 1.52, Q7 1.54, Q8 1.31,
Q9 1.65, Q10 1.24). Files, ranks and scores identical to the first run,
so found 9/10 (Q7 the miss) is repeatable.

### qmd from the shell, `qmd query`, same 10 questions, 2026-09-24
**0/10 returned anything.** Each call died at "Reranking 27 chunks" with
`ggml_vulkan: Device memory allocation of size 633207232 failed`
(`ErrorOutOfDeviceMemory`); rc=1, 35–126 s per call (Q3 rc=127, killed).
`qmd doctor` at the same time reported the GPU fine (10.9 GB free). The
`--no-gpu` run was stopped by hand after Q1 had sat at the rerank step
for over 10 minutes while a second qmd run was competing for the CPU; it
is not a clean measurement.
