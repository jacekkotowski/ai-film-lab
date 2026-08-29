# AI Film Lab — the whole thing, explained simply

You give it photographs and video clips. It gives you back a short film
with camera movement, music, and captions — like a professional editor
made it, not a slideshow.

This one document is everything you need. Nothing else to read first.

---

# PART 1 — Install (10 minutes, once)

## 1. Open PowerShell

Press the Windows key, type `powershell`, press Enter. A window opens.
Everything in this guide happens by typing into that window and
pressing Enter after each line.

## 2. Install two small programs

Copy each line below, paste it into the window (right-click pastes),
press Enter, and wait for it to finish before pasting the next one.

```powershell
winget install --id astral-sh.uv -e
```

```powershell
winget install --id Gyan.FFmpeg -e
```

If it asks you to agree to something, type `Y` and press Enter.

## 3. Close the window and open a new one

This matters — a window that was already open can't see programs
installed after it opened. Close PowerShell completely. Open it again
the same way as step 1.

## 4. Check it worked

```powershell
uv --version
```
```powershell
ffmpeg -version
```

Each should print a version number. If `ffmpeg -version` says it can't
be found, close and reopen PowerShell one more time — this fixes it
almost always.

## 5. Unpack the toolkit

Find `AI-Film-Lab.zip` in your Downloads folder, then:

```powershell
Expand-Archive "$HOME\Downloads\AI-Film-Lab.zip" -DestinationPath "$HOME" -Force
```

This creates a folder called `AI-Film` in your home folder. You're done
installing. **You will never do Part 1 again.**

---

# FILL IN YOUR LIBRARY (5 minutes, once)

```powershell
uv run film library
```

A folder opens with two folders inside it. What you put here is used by
**every film you will ever make**, so you only do this once:

- `music\` — one piece of music you like. Every film gets it: cut to the
  exact length, faded in and out, and turned down while you're talking.
- `cover\` — two pictures for the YouTube thumbnail. One **wide**
  (landscape) and one **tall** (portrait). Each film takes whichever of
  the two is its shape and prints the film's name on it. A `.jpg`, a
  `.png` or a `.gif` all work.

That second folder does two jobs. The same picture with the same words
on it becomes the **thumbnail** you upload, *and* the **first four
seconds of the film** — so somebody who clicks the miniature lands on
the frame they clicked. The opening card is an ordinary shot in
`film.yaml` called `s00`: change its `duration:` if four seconds is
wrong, or delete the block if you would rather open on yourself talking.

That's it. From now on, making a film is one folder of photos and one
command. Nothing ever asks you for music or a thumbnail again.

If one particular film wants its own music or its own cover picture, put
it in **that film's** `music\` or `cover\` folder — a film's own folder
always beats the library.

---

# THE ONE COMMAND TO REMEMBER

```powershell
uv run film
```

Nothing after the word `film`. It looks at where you are, works out what
the next step is, shows you the command in full, and offers to run it —
press ENTER and it does. Press ENTER enough times and you have a film.

It always prints the command before running it, so after a few films
you'll know them by heart and can stop asking. And every other command
ends the same way, with the next step on screen — so wherever you land,
just do what it says.

At every step it also offers **`C` for Claude**, if you have it
installed. That's for when something feels wrong and you'd rather say so
than work out which number to change:

> *shot 2 is too long and the camera move is too aggressive*

Any language — it doesn't have to be English. Type `/exit` when you're
done and you land back in the same walk-through, at whatever step you're
now on.

**In RStudio, use the Terminal pane, not the Console.** The Console can
run these too (`system("uv run film")`), but it can't answer questions,
so you'd only see the suggestion, not be able to say yes to it.

If you're working on several films, name the one you mean:

```powershell
uv run film next -p morning01
```

---

# IF YOU NEVER WANT TO TYPE ANYTHING

**Double-click `FILM.bat`.** That's the whole interface. There is only
one file to double-click, and it is that one.

It asks for a name, opens **one** folder, and waits:

- `media\` — drop your photos, your clips, your AI-made intro

Music and the thumbnail come from your library and need no attention.

Drag your things in, press ENTER, and it builds a draft and plays it in
well under a minute. Then it asks whether to make the full-quality
`final.mp4`. Press ENTER again and it does.

Every time after that, double-click `FILM.bat` and it picks up exactly
where you left off.

**Drag files straight onto `FILM.bat`** and it makes a film out of
exactly those, named for today, and builds it. Photos and clips go to
`media\`, an mp3 goes to `music\`, your originals are never moved. That
is the shortest path there is: select, drag, watch.

**To start another film, press `N`.** It's on offer at every step,
including on a film you've already finished — that's how you get out of
one and into a new one. `F` switches between films you've already
started, and shows you which are done. You can also name one directly:
`FILM.bat morning01`.

It is the same thing as typing `uv run film` — one door for people who
would rather not open a terminal, one for people who would.

**Running it again keeps your changes.** Once a film has a `film.yaml`,
it is left alone — every duration you tuned, every focus point you
clicked in the bench, every caption you reworded survives. If you want
it to forget everything and start over from the media, run
`uv run film go -p morning01 --rewrite`; the old file is kept next to
it as `film.yaml.bak`.

## If you talked while you filmed

That changes what happens to the clip, and it's the difference between a
film and a slideshow.

**A clip with sound on it is kept.** Not sampled — kept. What you said is
the point of it, so all of it stays, top to tail.

**The dead air comes out.** Any pause longer than about a second is cut,
leaving a quarter-second breath either side so no word gets clipped.
Short pauses stay, because speech without them sounds panicked. Each
remaining piece becomes its own shot, which is why the framing shifts on
every cut — that's what makes it read as an edit rather than a stumble.

A 25-second take where you talked, paused, talked, paused, talked comes
out as three shots and about 18 seconds, with every word still in it.
Each one carries a `note:` in `film.yaml` saying exactly what happened.

**Those joins get a short dissolve, and only those.** A hard cut back to
the same face half a second later reads as a stumble, so where a pause
was removed the two pieces blend over about a third of a second — with
the camera still travelling through it. Everywhere else in the film, a
cut is a cut. It's the `dissolve:` line on the shot; set it to `0` for a
hard cut, or raise it if you want the join softer.

**Quiet speech is safe.** The threshold for "silence" is measured on each
clip, against that clip's own average level — a sentence spoken softly is
not a pause. And if trimming ever wanted to remove more than a third of a
take, it decides the detection was wrong and keeps the take whole.

**The music gets out of the way while you talk** and comes back up in the
gaps. That's `music_duck:` in `film.yaml` — `0.3` by default, `0` to
switch it off, higher to push the music further down.

**A silent clip is treated as B-roll** and sampled for a few good
seconds, exactly as before. Nothing you said is ever sampled.

If a take drags, shorten it: change its `in:` or `out:` in `film.yaml`,
or just tell Claude *"the second bit of the statement is too slow."*

## Making it a particular length

```powershell
uv run film go -p my_movie --target 45
```

It shortens the photographs and, if that is not enough, leaves out the
weakest ones -- the ones with no face that are not opening, closing or
carrying a quote. **It never shortens anything you said.** If your
talking alone is already longer than the target, it says so in
`film.yaml` and leaves your words alone:

```
# You talk for 76s, which is already past the 45s target -- so the
# pictures were cut to the bone and nothing you said was touched.
```

Worth knowing: a Short is 60 seconds. Above that it is a normal video.

## If something looks wrong before you start

```powershell
uv run film doctor -p my_movie
```

Checks the boring things -- ffmpeg, what is in your folders, disk space,
whether captions are installed -- and says what is missing. `go` runs it
for you and stops early rather than failing two minutes into a render.

## iPhone photos

They arrive as `.HEIC`, which nothing else here can open. They're
converted to jpg automatically the first time you build — your originals
in `media\` are never touched. Anything that genuinely can't be read is
now named on screen instead of quietly vanishing.

Name files to control the order without opening anything:

| name it | you get |
|---|---|
| `00_`, `01_`, `02_` | exact order |
| `open_close_x.png` | same image opens **and** closes the film |
| `quote_stay_curious.png` | held card, filename becomes the text |

New films default to the `old_film` look — grain, soft vignette, a
little scratch, warm shadows — with shadow lift on. Change one line in
`film.yaml` if you want `clean`, `warm`, or `projector` instead.

---

# THE FAST PATH — one command

Once installed (Part 1), a whole short takes three lines:

```powershell
cd "$HOME\AI-Film"
uv run film new morning --vertical
explorer projects\morning\media
```

Drop your photos and clips in `media\`. Then:

```powershell
uv run film go -p morning
```

That single command looks at your material, writes the edit,
transcribes what you said into captions, and renders it — with your
speech kept, and the music from your library underneath, trimmed and
faded to the exact length of the film. Add `--final` when you want full
quality, which also builds the thumbnail.

`--vertical` makes it 1080x1920 for YouTube Shorts. Leave it off for
normal widescreen.

Naming files gives you control without opening anything:

| name it | you get |
|---|---|
| `00_`, `01_`, `02_` | exact order |
| `open_close_x.png` | same image opens **and** closes the film |
| `quote_stay_curious.png` | held title card, filename becomes the text |

---

# PART 2 — Step by step (if you'd rather go slowly)

## 6. Go into the toolkit folder

```powershell
cd "$HOME\AI-Film"
```

You'll do this one line every time you open a new PowerShell window and
want to work on a film. It's the only thing you repeat between sessions.

## 7. Create a project

A "project" is just a folder that holds one film's worth of material.

```powershell
uv run film new my_movie
```

The first time you run any `uv run film ...` command, it takes a
minute or two — it's quietly downloading Python and four small helper
packages. It only does this once, ever. After that, every command is
fast.

You can pick any name instead of `my_movie` — just remember what you
typed, because you'll use it again in every command below.

## 8. Add your photos and videos

```powershell
explorer projects\my_movie\media
```

A normal Windows Explorer window opens. **Drag your photos and video
clips into it.** Start small — 8 to 15 photos, one or two short clips.
Your original files are never changed or moved; the toolkit only ever
reads them.

## 9. Let it look at everything

```powershell
uv run film ingest -p my_movie
```

This looks at every photo and clip: finds faces, works out what's
probably the interesting part of each picture, and — for video —
detects where the cuts are. Takes a few seconds for photos, a bit
longer for video (it makes a small fast-preview copy of each clip).

## 10. Let it write a first edit

```powershell
uv run film init -p my_movie
```

This is the important one. It writes a file called `film.yaml` — a
complete description of your film: what order things play in, how long
each piece is on screen, which direction the camera drifts, where it's
looking. It picks all of this on its own, using what it learned in the
step above. **You have not made any decisions yet, and that's fine.**

## 11. Watch it

```powershell
uv run film peek -p my_movie
explorer projects\my_movie\out
```

Double-click `peek.mp4`. It's small and a little choppy on purpose —
built for speed, not beauty, so you can check it again and again without
waiting. **This is your first film.**

---

# PART 3 — Make it better

Everything from here is optional polish. Do as much or as little as you like.

## See it as a timeline you can click

```powershell
uv run film edit -p my_movie
```

Your web browser opens. You'll see every shot laid out left to right,
sized by how long it plays. Click a shot to select it. **Click on the
photo itself to tell the camera what to look at** — this is the single
most useful thing here; a face or the main subject, clicked directly,
looks far better than a guess. Drag a shot's right edge to make it
longer or shorter. Click **Save and peek** to see the result without
leaving the page.

**Nothing you change is in the film until you render again.** The page
says so rather than leaving you to remember it: the moment you change
anything, the video greys out under the words *"Changed since this was
rendered"*, the header says **edited — not rendered yet**, and the
**Save and peek** button starts pulsing. Press it and the button reads
*Rendering peek… 4s* while it works, then the new film scrolls into view.
When the video is bright, what you are watching is what you have.

Nothing is uploaded anywhere — this page is served from your own
computer, for your eyes only.

## Add captions from your own talking

You don't need to record anything separate. **If you're already talking
in your video clips, it uses that.** It listens to each clip that has
sound, works out what you said and exactly when, and writes it as
captions — you never type a timestamp by hand.

```powershell
uv sync --extra voice
uv run film caption -p my_movie
```

The first line installs one extra piece just for this feature (about
100 MB — that's why it's not there by default). The second one shows
you a preview of what it heard and where it would place it:

```
2 caption(s) matched to 1 shot(s).
  [s01] at   0.0s  "Here at the harbour the boats come in early."
  [s01] at   1.9s  "This is where my grandfather used to work every morning."
```

If that looks right:

```powershell
uv run film caption -p my_movie --apply
uv run film peek -p my_movie
```

**Prefer a separate voiceover instead of the clip's own sound?** Record
it on your phone, drop it into `projects\my_movie\media` named
`voiceover.mp3` (or `.wav`, `.m4a`), and run the same command — a file
named `voiceover.*` always takes priority over your clips' own audio.

**If a caption comes out wrong** — a misheard word, or wording you'd
rather change — open `film.yaml`, find the line under that shot's
`captions:`, and edit the `text:` directly. No need to re-run anything
except:

```powershell
uv run film peek -p my_movie
```

This all runs entirely on your own computer. Nothing you say is
uploaded anywhere.

## Filters -- scratches, projector look, better lighting

Open `film.yaml`, find the `look:` block near the top, and replace it
with one line:

```yaml
look:
  preset: old_film
```

Options: `clean` (barely graded), `warm`, `old_film` (grain, scratches,
a slight flicker, warm shadows), `projector` (all of that, heavier).
Run `uv run film peek -p my_movie` to see it.

**Want better-looking light, on real footage you can't reshoot?** Add
`glow` to lift shadow detail without blowing out anything bright:

```yaml
look:
  preset: old_film
  glow: 0.4
```

Any field after `preset:` overrides just that one thing — everything
else from the preset stays.

## Turn your data into a shot

You're in RStudio, so your data is right there. Save whatever you want
to show as a plain CSV, in this shape -- one row per time step per
series:

```
time,series,value
2019,Revenue,120
2020,Revenue,210
2021,Revenue,340
```

Then:

```powershell
uv run film data-clip projects\my_movie\media\growth.csv -p my_movie --kind line --seconds 4
```

This writes an mp4 clip -- a line growing, bars racing, or one big
number climbing, matched to your film's size, frame rate, and dark
background. It prints exactly what to paste into `film.yaml`:

```yaml
  - src: media/growth.mp4
    duration: 4.0
    move: static
```

Drop that in wherever the data beat belongs in your sequence, run
`uv run film peek -p my_movie`, and it plays like any other shot.

`--kind` options: `line` (a trend building), `bar_race` (values
reordering as they change), `counter` (one number climbing to its
final value — good for a single headline figure).

From R, write the CSV with `write.csv(df, "media/growth.csv",
row.names = FALSE)` and you're already there — no extra conversion.

## When you're happy: full quality

```powershell
uv run film draft -p my_movie
```

Better quality, still fast — under a minute. Once that looks right:

```powershell
uv run film final -p my_movie
```

Full quality. Takes a few minutes. This is the one you actually keep
and share.

**The thumbnail is made at the same time**, without you asking:
`out\cover.jpg`, the film's name over the picture from your library that
matches the film's shape, sized for YouTube and kept under its 2 MB
limit. Upload it next to the mp4.

To change the words on it, put a `title:` line at the top of `film.yaml`:

```yaml
title: Zima nad morzem
```

Without one, the film is called what its folder is called. To try one
without rendering again:

```powershell
uv run film cover -p my_movie --title "Something else"
```

A cover you made by hand that way is never overwritten by a later
render, unless you edit `film.yaml` afterwards.

---

# PART 4 — Ask an AI to make the editing decisions for you

Everything above, you can also do by just describing what you want in
plain English, and letting Claude do the typing and the taste.

## Install it (once)

```powershell
irm https://claude.ai/install.ps1 | iex
```

## Use it

```powershell
cd "$HOME\AI-Film"
claude
```

The window changes — now you're talking, not typing commands. Try:

> Ingest my_movie, write a first film.yaml, and show me a peek.

> Shot 2 is too long and the camera move is too aggressive. Fix it and
> render again.

> Look at the contact sheet for my_movie and tell me what you see.

Claude runs the actual commands for you and reports back. When you're
done, type:

```
/exit
```

and you're back to typing commands yourself.

**You never have to use this.** Everything in Part 2 and 3 works
completely on its own, with no AI involved at all.

---

# If something goes wrong

**"uv: command not found" or similar** — close PowerShell completely
and open a new one. New installs are invisible to old windows.

**"No project found for..."** — you're either not inside `AI-Film`, or
you haven't run `uv run film new my_movie` yet. Run:
```powershell
cd "$HOME\AI-Film"
```
then try again.

**Any other error** — copy the exact red text and paste it into a
message. Don't summarize it or describe it — the exact words matter.

---

# The one file worth understanding: `film.yaml`

If you ever want to hand-edit instead of using the browser page, open
`projects\my_movie\film.yaml` in Notepad. It's a plain list of shots —
which picture, how long, which way the camera moves. Change a number,
save, and run `uv run film peek -p my_movie` again to see the result.

After any hand edit, run this — it checks your file and tells you, in
plain language with a line number, if something's wrong:

```powershell
uv run film check -p my_movie
```

## If a change made it worse

Every render quietly saves your `film.yaml` first, but only when it
actually changed. So there's a list of every version you've ever looked
at, newest at the top:

```powershell
git log --oneline -- projects\my_movie\film.yaml
```

Each line starts with a short code. To go back to one of them:

```powershell
git show a6511a2:projects/my_movie/film.yaml > projects/my_movie/film.yaml
```

Then `uv run film peek -p my_movie` and you're looking at the old
version again. Nothing else in your work is touched, and your photos and
clips are never in here — git tracks the *edit*, not the footage.

That's the whole system.
