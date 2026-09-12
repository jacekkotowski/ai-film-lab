# AI Film Lab — what it actually does

You put photographs and video clips in a folder. It gives you back a
short film — with camera movement, music, and captions taken from your
own talking.

Nothing is uploaded. No account. Once it is installed it needs no
internet at all.

This document explains what the program *does*.
[HOW_TO_USE.md](HOW_TO_USE.md) explains how to *run* it, and assumes
nothing.

---

## The idea

The film is a **text file** called `film.yaml` — a list of shots, how
long each one holds, which way the camera drifts, what the caption says.
You can open it, read it, change a number, and look again.

That is the whole trick. There is no project file you can only open in
one program. If a shot feels too long, you change `6.0` to `4.5`. Every
render saves the file first, so `film undo` can always put back the last
version you watched.

---

## What it does to the picture

### 1. It looks at your material first

It reads every photo and clip once and writes down what it found: a
contact sheet of everything, **where the faces are** so portraits get
framed on the face instead of the middle, where one shot ends and the
next begins inside a video, and **where you are talking and where you
paused**.

It also makes small 480p copies, so that previews are quick. The answers
are cached per file — dropping one new clip into a folder of forty does
not re-examine the other thirty-nine.

### 2. It writes a first edit

Order, how long each shot holds, which camera move, and where the dead
air comes out. Shots with a face are held longer than shots without. A
long take is cut at your own pauses, never mid-word.

Treat this as a rough draft to improve, not as the answer.

### 3. The camera move

There is no zooming of the file. A **crop window** is moved across the
picture and the frame is sampled through it — pushing in, panning,
drifting, with a fraction of a degree of roll. It is sub-pixel accurate,
which is why the motion is smooth rather than steppy, and the window
never sits at full size, so there is always room to move.

Motion blur is added **only where something actually moves**. A slow
drift travels less than a pixel per frame, and blurring that four ways
would be wasted work.

A wide photograph in a tall frame can sit whole on a blurred copy of
itself instead of having its sides cut off.

### 4. The look, and the words on screen

Four presets — `clean`, `warm`, `old_film`, `projector` — made of grain,
vignette, a lift in the shadows, a little flicker and the odd scratch.
Off by default; they are seasoning, not the meal.

Captions are set in the same typeface as the thumbnail, so the miniature
and the film look like one thing. Cuts are plain cuts; the only dissolve
is where a pause was removed, to cover the join.

---

## What it does to the sound

### 1. Your voice keeps its place

The speech recorded inside your clips is pulled out and each piece is put
back exactly where its shot sits in the finished film — counted in
**frames**, not seconds, so it cannot drift out of step with your lips
over a long film.

### 2. A take is shaped once, whole

Not piece by piece. The recording is continuous even though the picture
was cut, so the voice is treated as one continuous thing and the pieces
are cut out of the result. Shaping each piece separately put a small
burst of noise on every single join.

### 3. It measures your recording before it touches it

Every setting below is a level in decibels, and a level is meaningless
until you know how loudly the take was recorded. So the take is measured
first — **where the room sits and where the voice sits** — and everything
after that is worked out from those two numbers.

This is what lets one setting serve a take shouted at a phone and a take
murmured at a laptop.

### 4. Music that gets out of the way

One piece of music, kept in a shared folder, backs every film you make.
It is cut — or looped — to the film's exact length, faded at both ends,
and **ducked under your voice** automatically, which is what lets it be
properly present in the gaps.

### 5. Captions from what you actually said

Optional. It can transcribe your own speech and time the lines to the
moments you said them. The model downloads once, then runs on your
machine with no internet.

### The voice, filter by filter, in order

| | what it does | where |
|---|---|---|
| 1 | Cut out the rumble — desk thump, traffic, the fan, the microphone being handled | below 80 Hz |
| 2 | A little warmth in the chest register. This is what "deeper" actually is — EQ, not pitch | +2.5 dB @ 110 Hz |
| 3 | Bring the whole take to a known level — one flat gain, so the voice and the room move together | −20 LUFS |
| 4 | Take the hiss out, with the floor taken from this take's own measured room | measured |
| 5 | Shut the room off between words, set between this take's room and this take's voice | measured |
| 6 | Even out loud and quiet sentences — only the difference between leaning in and tailing off | up to 6 dB |
| 7 | Shut the gaps again after that, for anything the evener lifted | measured |
| 8 | Match the loudness of everything else online, so no player has to touch your mix | −14 LUFS |

−14 LUFS is what YouTube and Spotify normalise to.

---

## Look at it three ways

| command | how long | the question it answers |
|---|---|---|
| `film peek` | seconds | Is the **order** right? |
| `film draft` | under a minute | Does the **motion** feel right? |
| `film final` | several minutes | Ship it. Full resolution, from the originals. |

The middle one is where the work happens. Watch, change a number or two
in `film.yaml`, watch again. Expect to go round that loop many times — it
is the whole system.

---

## Getting it running

Windows, about ten minutes, once.

Download the folder from GitHub, unzip it, and double-click
**`FILM.bat`**. The first time, if it cannot find the two free programs
it needs, it prints two lines for you to paste — paste them, close the
window, double-click again. That happens once.

After that it asks for a name, opens a folder for your photos and clips,
and tells you the next step as it goes.
[HOW_TO_USE.md](HOW_TO_USE.md) is the full walkthrough.

- **Bring your own music and cover picture.** They are not in the
  download — they are personal files. Run `film library` once, drop in
  one piece of music and two pictures (one wide, one tall), and every
  film you ever make has both.
- **Your originals are never modified.** The folder you put them in is
  read-only to the program. It writes an edit, not a new copy of your
  footage.
- **It is four small packages.** Deliberately. Nothing phones home.

---

*Everything above is what the program actually does — the numbers are the
ones in the code, not round figures.*
