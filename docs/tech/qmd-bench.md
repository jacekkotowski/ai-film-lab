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
