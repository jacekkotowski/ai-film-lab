# AI Film Lab

Drop photographs and clips in a folder. Get a cinematic sequence out —
camera movement, music, captions from your own talking. It runs on your
own computer: nothing is uploaded, no account, no internet needed once
it's installed.

## Get it running (Windows)

1. Above, click **Code → Download ZIP**, then unzip it wherever you
   like. (`git clone` works too, if you'd rather.)
2. Double-click **`FILM.bat`**. The very first time, if it can't find
   the two free programs it needs, it prints two lines to paste into
   PowerShell — paste them, close the window, and double-click
   `FILM.bat` again. That only happens once.
3. It asks for a name, opens a folder for your photos and clips, and
   walks you through everything from there — one question at a time,
   telling you the next step as it goes.

**[Read HOW_TO_USE.md](HOW_TO_USE.md)** for the full walkthrough. It
assumes nothing, and it's the manual for everything below this point too.

---

## Set up once, then never again

```powershell
uv run film library
```

One folder holds the music and the two thumbnail pictures — one wide,
one tall — that **every** film uses. Fill it in once and no film ever
asks you for either again: the music is cut to length and ducked under
your voice, and `film final` prints the film's name on whichever
thumbnail picture matches its shape. A film with its own `music\` or
`cover\` folder overrides it.

## The three ways in, in order of effort

**Double-click `FILM.bat`.** It asks what you want, does it, and tells
you what is next. No terminal, no commands.

**Type `uv run film`.** The same thing, in a terminal — the RStudio
Terminal pane does fine. Every command it runs, it prints first, so you
learn them by using it.

**Type `claude`.** For the parts that need taste rather than steps:
*"shot 2 is too long and the camera move is too aggressive."* The
working agreement in [CLAUDE.md](CLAUDE.md) is what keeps it editing
the film instead of rewriting the machine.

## What it is

The film is a **document** — `film.yaml` — not a project file. You can
read it, diff it, and hand it to anyone:

```yaml
  - id: s04
    src: media/harbour.jpg
    duration: 6.0
    move: push_in
    focus: [0.42, 0.38]
    note: "held long -- this is the one that has to land"
```

Everything else is the machine that renders it. Four dependencies:
numpy, opencv, pillow, pyyaml. Start with [ffilm/spec.py](ffilm/spec.py)
— it says what a film *is*, and the rest follows from it.

Every render commits your `film.yaml` if it changed, so any version you
have ever watched can be brought back:

```powershell
git log --oneline -- projects/my_movie/film.yaml
```
