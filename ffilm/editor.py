"""
editor.py  --  a small local editing bench in your browser.

    uv run film edit

Opens a page on 127.0.0.1. Nothing leaves your machine, nothing is
downloaded, no new dependencies -- this is Python's own http.server.

What it is for: the two things that are genuinely painful to type by
hand. Setting a focus point (click the picture instead of guessing
`[0.42, 0.38]`) and judging duration (drag a frame instead of imagining
what 4.5 seconds feels like).

What it is NOT: Shotcut. No waveform, no frame-accurate scrubbing. It
edits film.yaml and nothing else, so you can use it, Notepad++, and
Claude on the same file interchangeably.

One warning it also prints on screen: saving rewrites film.yaml, so
`#` comments are lost. Use `note:` fields instead -- those are data and
survive.
"""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .moves import EASINGS, MOVES
from .spec import Film

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>film.yaml — editing bench</title>
<style>
:root{
  --table:#d7dcda;      /* light table glass */
  --panel:#f3f5f4;
  --edge:#b9c1be;
  --ink:#191d1c;
  --muted:#69736f;
  --cyan:#0e6f78;       /* film cyan dye layer */
  --strip:#2a2f2e;      /* filmstrip base */
  --r:3px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--table);color:var(--ink);
 font:14px/1.5 "Segoe UI",system-ui,sans-serif}
.mono{font-family:Consolas,ui-monospace,"DejaVu Sans Mono",monospace;
 font-variant-numeric:tabular-nums}
header{display:flex;align-items:baseline;gap:16px;padding:14px 20px;
 border-bottom:1px solid var(--edge)}
h1{font-size:14px;letter-spacing:.14em;text-transform:uppercase;margin:0;font-weight:600}
.total{font-size:12px;color:var(--muted)}
.grow{flex:1}
button{font:inherit;background:var(--panel);color:var(--ink);cursor:pointer;
 border:1px solid var(--edge);border-radius:var(--r);padding:5px 11px}
button:hover{border-color:var(--cyan)}
button:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}
button.primary{background:var(--cyan);border-color:var(--cyan);color:#fff}
button.primary:hover{filter:brightness(1.12)}

/* ---- the filmstrip: the one place this looks like nothing else ---- */
#strip{background:var(--strip);padding:9px 0;margin:0;overflow-x:auto;
 white-space:nowrap;border-bottom:1px solid var(--edge)}
#strip::before,#strip::after{content:"";display:block;height:7px;
 background-image:radial-gradient(var(--table) 45%,transparent 47%);
 background-size:15px 7px;background-repeat:repeat-x}
.frame{display:inline-block;vertical-align:top;height:74px;margin:5px 2px;
 position:relative;border:1px solid #444;background:#111;overflow:hidden;
 cursor:pointer;min-width:26px}
.frame img{height:100%;width:100%;object-fit:cover;display:block;opacity:.82}
.frame.sel{border-color:var(--cyan);box-shadow:0 0 0 2px var(--cyan)}
.frame .lab{position:absolute;left:0;bottom:0;right:0;font-size:10px;
 padding:1px 3px;background:rgba(0,0,0,.62);color:#e9edec}
.frame .grip{position:absolute;right:0;top:0;bottom:0;width:7px;
 cursor:ew-resize;background:linear-gradient(90deg,transparent,rgba(255,255,255,.28))}

main{display:grid;grid-template-columns:1fr 340px;gap:0;align-items:start}
@media(max-width:820px){main{grid-template-columns:1fr}}
#list{padding:14px 20px}
.shot{background:var(--panel);border:1px solid var(--edge);border-radius:var(--r);
 padding:10px 12px;margin-bottom:9px}
.shot.sel{border-color:var(--cyan)}
.shot h3{margin:0 0 8px;font-size:12px;letter-spacing:.1em;text-transform:uppercase;
 display:flex;gap:8px;align-items:center}
.shot h3 .src{color:var(--muted);text-transform:none;letter-spacing:0;font-weight:400;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px}
label{font-size:11px;color:var(--muted);letter-spacing:.05em}
input,select,textarea{font:inherit;background:#fff;color:var(--ink);
 border:1px solid var(--edge);border-radius:var(--r);padding:3px 6px}
input[type=number]{width:74px}
input[type=range]{padding:0;width:110px}
textarea{width:100%;resize:vertical}
aside{position:sticky;top:0;padding:14px 18px 24px;border-left:1px solid var(--edge)}
#pick{position:relative;display:inline-block;line-height:0;cursor:crosshair;
 border:1px solid var(--edge)}
#pick img{max-width:100%;display:block}
#cross{position:absolute;width:15px;height:15px;margin:-8px 0 0 -8px;pointer-events:none}
#cross::before,#cross::after{content:"";position:absolute;background:var(--cyan)}
#cross::before{left:7px;top:0;width:2px;height:15px}
#cross::after{top:7px;left:0;height:2px;width:15px}
video{width:100%;margin-top:10px;background:#000;border:1px solid var(--edge);display:block}

/* --- is what you are watching still the film you have? --------------
   The whole point of this page is a loop: change a number, look at it.
   That only works if it is obvious when the picture on screen is older
   than the numbers beside it. */
#vidwrap{position:relative;margin-top:10px}
#stale{position:absolute;inset:10px 0 0;display:none;place-content:center;
 text-align:center;background:rgba(20,24,23,.72);color:#fff;font-size:12px;
 letter-spacing:.04em;padding:8px}
#stale span{display:block;font-size:11px;opacity:.85;margin-top:3px}
body.dirty #stale{display:grid}
body.dirty #vid{opacity:.35}
#hstatus{font-size:12px;color:var(--muted)}
#hstatus.warn{color:#8a4b12;font-weight:600}
#hstatus.busy{color:var(--cyan);font-weight:600}
/* The one button that gets you out of a stale state, made obvious. */
body.dirty button.primary{animation:nudge 1.6s ease-in-out infinite}
@keyframes nudge{0%,100%{box-shadow:0 0 0 0 rgba(14,111,120,.55)}
                 50%{box-shadow:0 0 0 5px rgba(14,111,120,0)}}
button:disabled{opacity:.55;cursor:progress}
.hint{font-size:11px;color:var(--muted);margin:6px 0 0}
.caps{border-top:1px dashed var(--edge);margin-top:8px;padding-top:7px}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style></head><body>

<header>
  <h1>film.yaml</h1>
  <span class="total mono" id="total"></span>
  <span class="grow"></span>
  <span id="hstatus"></span>
  <button id="save">Save</button>
  <button id="peek" class="primary">Save and peek</button>
  <button id="draft">Save and draft</button>
  <button id="done" title="save, close the bench, and go back to the terminal">Done</button>
</header>

<div id="strip"></div>

<main>
  <div id="list"></div>
  <aside>
    <label>Focus point — click where the subject is</label>
    <div id="pick"><img id="pickimg" alt=""><div id="cross"></div></div>
    <p class="hint mono" id="focustxt"></p>
    <p class="hint">The camera moves <em>toward</em> this point. Putting it on
      a face is most of what makes a shot look composed.</p>
    <div id="vidwrap">
      <video id="vid" controls></video>
      <div id="stale">Changed since this was rendered<span>press <b>Save and peek</b></span></div>
    </div>
    <p class="hint" id="status"></p>
    <p class="hint">Saving rewrites film.yaml, so <code>#</code> comments are
      lost. Use <strong>note</strong> fields instead — they survive.</p>
  </aside>
</main>

<script>
let S=null, sel=0, MOVES=[], EASES=[];

const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

let rendered=null;      // the film.yaml the video on screen was made from

async function boot(){
  const r = await fetch("api/state"); S = await r.json();
  MOVES=S.moves; EASES=S.eases; rendered=snap(); render();
}

const snap = () => JSON.stringify(S.shots);

// Stale means: what you are watching is older than what you have edited.
// It is the single most important thing this page can tell you, so it is
// said three times -- in the header, over the video, and on the button.
function freshness(){
  const dirty = rendered!==null && snap()!==rendered;
  document.body.classList.toggle("dirty", dirty);
  const h=document.getElementById("hstatus");
  if(h.classList.contains("busy")) return;
  if(dirty){ h.className="warn"; h.textContent="edited — not rendered yet"; }
  else if(h.classList.contains("warn")){ h.className=""; h.textContent=""; }
  // Otherwise leave what is there -- it is the "ready in 12s" line, and
  // clearing it the instant the render finished was how the old page
  // managed to look like it had done nothing at all.
}

function setStatus(t, busy){
  const h=document.getElementById("hstatus");
  h.className = busy ? "busy" : "";
  h.textContent = t;
  document.getElementById("status").textContent = t;
}

function total(){ return S.shots.reduce((a,s)=>a+(+s.duration||0),0); }

function render(){
  document.getElementById("total").textContent =
    S.shots.length+" shots · "+total().toFixed(1)+"s · "+S.width+"×"+S.height+" @"+S.fps+"fps";
  strip(); list(); picker(); freshness();
}

function strip(){
  const el=document.getElementById("strip"); el.innerHTML="";
  const inner=document.createElement("div");
  S.shots.forEach((s,i)=>{
    const d=document.createElement("div");
    d.className="frame"+(i===sel?" sel":"");
    d.style.width = Math.max(26, (+s.duration||1)*26)+"px";
    d.tabIndex=0;
    d.innerHTML = (s.thumb?`<img src="thumb/${encodeURIComponent(s.thumb)}" alt="">`:"")
      + `<span class="lab mono">${esc(s.id)} ${(+s.duration||0).toFixed(1)}s</span>`
      + `<span class="grip" title="drag to change duration"></span>`;
    d.onclick=()=>{sel=i;render();};
    d.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();sel=i;render();}};
    d.querySelector(".grip").onmousedown=e=>drag(e,i,d);
    inner.appendChild(d);
  });
  el.appendChild(inner);
}

function drag(e,i,el){
  e.stopPropagation(); e.preventDefault();
  const x0=e.clientX, d0=+S.shots[i].duration||1;
  const mv=ev=>{
    const d=Math.max(0.4, d0+(ev.clientX-x0)/26);
    S.shots[i].duration=Math.round(d*10)/10;
    el.style.width=Math.max(26,S.shots[i].duration*26)+"px";
    el.querySelector(".lab").textContent=S.shots[i].id+" "+S.shots[i].duration.toFixed(1)+"s";
    document.getElementById("total").textContent =
      S.shots.length+" shots · "+total().toFixed(1)+"s · "+S.width+"×"+S.height+" @"+S.fps+"fps";
  };
  const up=()=>{document.removeEventListener("mousemove",mv);
    document.removeEventListener("mouseup",up); render();};
  document.addEventListener("mousemove",mv); document.addEventListener("mouseup",up);
}

function list(){
  const el=document.getElementById("list"); el.innerHTML="";
  S.shots.forEach((s,i)=>{
    const c=document.createElement("div");
    c.className="shot"+(i===sel?" sel":"");
    c.onclick=()=>{if(sel!==i){sel=i;render();}};
    const isVid = s.kind==="video";
    c.innerHTML=`
      <h3><span class="mono">${esc(s.id)}</span>
          <span class="src">${esc(s.src)}</span>
          <span class="grow" style="flex:1"></span>
          <button data-a="up" ${i===0?"disabled":""} title="move earlier">↑</button>
          <button data-a="dn" ${i===S.shots.length-1?"disabled":""} title="move later">↓</button>
          <button data-a="del" title="remove shot">×</button></h3>
      <div class="row">
        <label>move</label>
        <select data-f="move">${MOVES.map(m=>`<option${m===s.move?" selected":""}>${m}</option>`).join("")}</select>
        <label>ease</label>
        <select data-f="ease">${EASES.map(m=>`<option${m===s.ease?" selected":""}>${m}</option>`).join("")}</select>
        <label>amount</label>
        <input type="range" min="0.2" max="1.6" step="0.05" value="${s.amount??1}" data-f="amount">
        <span class="mono" data-o="amount">${(+(s.amount??1)).toFixed(2)}</span>
      </div>
      <div class="row">
        <label>seconds</label>
        <input type="number" step="0.1" min="0.4" value="${(+s.duration||0).toFixed(1)}" data-f="duration">
        ${isVid?`<label>starts at</label><input type="number" step="0.1" min="0" value="${(+s.tin||0).toFixed(1)}" data-f="tin">`:""}
        <label>focus</label><span class="mono">${(+s.focus[0]).toFixed(3)}, ${(+s.focus[1]).toFixed(3)}</span>
      </div>
      <div class="row"><label>note</label>
        <input style="flex:1" data-f="note" value="${esc(s.note)}" placeholder="why this shot is this long"></div>
      <div class="caps" data-caps></div>`;
    caps(c.querySelector("[data-caps]"), s, i);
    c.querySelectorAll("[data-f]").forEach(inp=>{
      const ev = inp.type==="range"?"input":"change";
      inp.addEventListener(ev,e=>{
        e.stopPropagation();
        const f=inp.dataset.f;
        let v=inp.value;
        if(["duration","amount","tin"].includes(f)) v=parseFloat(v)||0;
        S.shots[i][f]=v;
        if(f==="amount"){c.querySelector('[data-o="amount"]').textContent=(+v).toFixed(2);}
        else render();
      });
    });
    c.querySelectorAll("[data-a]").forEach(b=>b.addEventListener("click",e=>{
      e.stopPropagation();
      const a=b.dataset.a;
      if(a==="del") S.shots.splice(i,1);
      if(a==="up"){ [S.shots[i-1],S.shots[i]]=[S.shots[i],S.shots[i-1]]; sel=i-1; }
      if(a==="dn"){ [S.shots[i+1],S.shots[i]]=[S.shots[i],S.shots[i+1]]; sel=i+1; }
      if(sel>=S.shots.length) sel=Math.max(0,S.shots.length-1);
      render();
    }));
    el.appendChild(c);
  });
}

function caps(box,s,i){
  box.innerHTML = `<div class="row"><label>captions</label>
    <button data-add>add caption</button></div>` +
    s.captions.map((c,j)=>`<div class="row">
      <input style="flex:1" data-c="${j}" data-k="text" value="${esc(c.text)}" placeholder="what this stresses">
      <label>at</label><input type="number" step="0.1" data-c="${j}" data-k="at" value="${c.at}">
      <label>for</label><input type="number" step="0.1" data-c="${j}" data-k="dur" value="${c.dur}">
      <select data-c="${j}" data-k="pos">${["bottom","lower_third","top","center"]
        .map(p=>`<option${p===c.pos?" selected":""}>${p}</option>`).join("")}</select>
      <button data-rm="${j}">×</button></div>`).join("");
  box.querySelector("[data-add]").onclick=e=>{e.stopPropagation();
    s.captions.push({text:"",at:0.5,dur:2.5,pos:"bottom"});render();};
  box.querySelectorAll("[data-c]").forEach(inp=>inp.addEventListener("change",e=>{
    e.stopPropagation();
    const j=+inp.dataset.c,k=inp.dataset.k;
    s.captions[j][k] = (k==="at"||k==="dur")?parseFloat(inp.value)||0:inp.value;
  }));
  box.querySelectorAll("[data-rm]").forEach(b=>b.addEventListener("click",e=>{
    e.stopPropagation(); s.captions.splice(+b.dataset.rm,1); render();}));
}

function picker(){
  const s=S.shots[sel]; if(!s) return;
  const img=document.getElementById("pickimg");
  img.src = s.thumb?("thumb/"+encodeURIComponent(s.thumb)):"";
  document.getElementById("focustxt").textContent =
    "focus: ["+(+s.focus[0]).toFixed(3)+", "+(+s.focus[1]).toFixed(3)+"]";
  place();
  img.onload=place;
  document.getElementById("pick").onclick=e=>{
    const r=img.getBoundingClientRect(); if(!r.width) return;
    s.focus=[Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),
             Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))];
    render();
  };
}
function place(){
  const s=S.shots[sel], img=document.getElementById("pickimg");
  const c=document.getElementById("cross");
  c.style.left=(s.focus[0]*img.clientWidth)+"px";
  c.style.top =(s.focus[1]*img.clientHeight)+"px";
}

const BUTTONS = ["save","peek","draft"];
function busy(on, label){
  BUTTONS.forEach(id=>{
    const b=document.getElementById(id);
    b.disabled=on;
    if(id!=="save"){ b.dataset.label = b.dataset.label || b.textContent; }
  });
  if(label){ document.getElementById("peek").textContent=label; }
  else { BUTTONS.forEach(id=>{const b=document.getElementById(id);
         if(b.dataset.label) b.textContent=b.dataset.label;}); }
}

async function save(quiet){
  const r=await fetch("api/save",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(S)});
  const j=await r.json();
  if(!quiet) setStatus(j.ok?("Saved "+new Date().toLocaleTimeString()):("NOT saved — "+j.error));
  return j.ok;
}

async function run(q){
  busy(true, "Rendering "+q+"…");
  setStatus("Saving…", true);
  if(!await save(true)){ busy(false); freshness(); return; }
  // A render is ten to sixty seconds of nothing. Say so where the eye is,
  // count it, and put the finished film in front of them at the end --
  // the old version said "Rendering…" in 11px text a thousand pixels
  // down the page, which reads exactly like a button that does nothing.
  let n=0;
  const tick=setInterval(()=>{setStatus("Rendering "+q+"… "+(++n)+"s", true);},1000);
  let j;
  try{
    const r=await fetch("api/render?q="+q,{method:"POST"}); j=await r.json();
  }catch(e){ j={ok:false,error:String(e)}; }
  clearInterval(tick);
  busy(false);
  if(j.ok){
    rendered = snap();
    const v=document.getElementById("vid");
    v.src=j.url+"?t="+Date.now();
    v.scrollIntoView({block:"center", behavior:"smooth"});
    v.play().catch(()=>{});
    setStatus(q+" ready in "+j.secs+"s — this is what you just edited");
  } else {
    setStatus("Render failed — "+j.error);
  }
  freshness();
}
// The way out. Ctrl+C in the terminal works too, but inside FILM.bat it
// asks Windows to terminate the batch job, which closes the whole
// window and takes the guide with it -- so the honest exit is here.
document.getElementById("done").onclick=async()=>{
  await save(true);
  try{ await fetch("api/quit",{method:"POST"}); }catch(e){}
  document.body.innerHTML=
    '<div style="display:flex;height:100vh;align-items:center;'
    +'justify-content:center;text-align:center;line-height:1.7">'
    +'<div><div style="font-size:26px">Saved.</div>'
    +'<div style="opacity:.7;margin-top:10px">The bench is closed. '
    +'You can shut this tab.<br>Your film is waiting in the terminal.'
    +'</div></div></div>';
};
document.getElementById("save").onclick=()=>save();
document.getElementById("peek").onclick=()=>run("peek");
document.getElementById("draft").onclick=()=>run("draft");
window.addEventListener("resize",place);
boot();
</script></body></html>
"""


# --------------------------------------------------------------------------


def thumb_map(project: Path) -> dict[str, str]:
    mf = project / "analysis" / "manifest.json"
    if not mf.exists():
        return {}
    data = json.loads(mf.read_text(encoding="utf-8"))
    return {e["path"]: e.get("thumb", "") for e in data.get("media", [])}


def state(project: Path) -> dict:
    film = Film.load(project / "film.yaml")
    thumbs = thumb_map(project)
    shots = []
    for s in film.shots:
        shots.append({
            "id": s.id, "src": s.src, "kind": s.kind,
            "duration": round(s.duration, 2), "tin": round(s.tin, 2),
            "speed": s.speed, "move": s.move if s.move != "auto" else "drift_right",
            "ease": s.ease, "amount": s.amount,
            "focus": list(s.focus or (0.5, 0.5)), "note": s.note,
            "thumb": thumbs.get(s.src, ""),
            # Carried, not edited. The bench has no controls for these and
            # must hand them back exactly as it found them -- `dissolve`
            # softens the joins where a pause was cut, and from/to are the
            # windows somebody tuned by hand and does not want guessed at.
            "dissolve": s.dissolve,
            "fill": s.fill,
            "frm": None if s.frm is None else vars(s.frm),
            "to": None if s.to is None else vars(s.to),
            "captions": [{"text": c.text, "at": c.at, "dur": c.dur, "pos": c.pos}
                         for c in s.captions],
        })
    return {"fps": film.fps, "width": film.width, "height": film.height,
            "audio": film.audio, "shots": shots,
            "moves": MOVES, "eases": sorted(EASINGS)}


def dump(project: Path, data: dict) -> str:
    """The whole film.yaml, rewritten.

    Everything the bench does NOT edit is carried across untouched, by
    reading the file and passing the rest through. It used to write out a
    fixed list of keys instead, which meant one click of Save silently
    deleted whatever had been added since the bench was written -- the
    music level, the ducking, the loudness, and three quarters of the
    `look`. The bench only knows about shots; it has no business having an
    opinion on the rest of the file.
    """
    import yaml

    raw = yaml.safe_load(
        (project / "film.yaml").read_text(encoding="utf-8")) or {}
    MANAGED = {"fps", "resolution", "shots"}
    rest = {k: v for k, v in raw.items() if k not in MANAGED}

    L = ["# Edited in `film edit`. Comments are not preserved by the editor —",
         "# use `note:` fields, which are data and survive.", "",
         f"fps: {data['fps']}",
         f"resolution: [{data['width']}, {data['height']}]"]
    if rest:
        L.append("")
        L.append(yaml.safe_dump(rest, sort_keys=False, allow_unicode=True,
                                width=90).rstrip())
    L += ["", "shots:"]

    for i, s in enumerate(data["shots"], 1):
        dur = max(0.4, float(s["duration"]))
        L.append("")
        L.append(f"  - id: s{i:02d}")
        L.append(f"    src: {s['src']}")
        if s["kind"] == "video":
            tin = max(0.0, float(s.get("tin", 0.0)))
            L.append(f'    in: "{int(tin // 60):02d}:{tin % 60:05.2f}"')
            speed = float(s.get("speed", 1.0))
            out = tin + dur * speed
            L.append(f'    out: "{int(out // 60):02d}:{out % 60:05.2f}"')
            # Carried, not edited -- and it has to be written back or it
            # is lost. The bench computes `out` FROM the speed, so a
            # dropped `speed: 1.2` does not merely revert: the shot keeps
            # the longer out-point and plays it at 1.0, quietly growing
            # by 20% the first time you save.
            if abs(speed - 1.0) > 0.001:
                L.append(f"    speed: {speed}")
        else:
            L.append(f"    duration: {dur:.1f}")
        L.append(f"    move: {s['move']}")
        L.append(f"    ease: {s['ease']}")
        if abs(float(s.get("amount", 1.0)) - 1.0) > 0.001:
            L.append(f"    amount: {float(s['amount']):.2f}")
        L.append(f"    focus: [{float(s['focus'][0]):.3f}, {float(s['focus'][1]):.3f}]")
        if float(s.get("dissolve", 0) or 0) > 0:
            L.append(f"    dissolve: {float(s['dissolve'])}")
        if s.get("fill"):
            L.append(f"    fill: {s['fill']}")
        for key, win in (("from", s.get("frm")), ("to", s.get("to"))):
            if win:
                L.append(f"    {key}:")
                for k in ("cx", "cy", "scale", "roll"):
                    L.append(f"      {k}: {float(win[k]):.4f}")
        if s.get("note"):
            L.append(f"    note: {json.dumps(s['note'])}")
        caps = [c for c in s.get("captions", []) if str(c.get("text", "")).strip()]
        if caps:
            L.append("    captions:")
            for c in caps:
                # Rounded to a tenth for legibility, then clamped to the
                # shot -- in that order. Rounding `at` and `dur` up
                # independently is how one drag of a duration grip wrote
                # a caption six hundredths of a second past the end of
                # its shot, and a film that then would not load at all.
                at = min(round(float(c["at"]), 1), dur)
                cap_dur = min(round(float(c["dur"]), 1), dur - at)
                if cap_dur <= 0:
                    continue                 # nothing of it is left on screen
                L.append(f"      - text: {json.dumps(c['text'])}")
                L.append(f"        at: {at:.1f}")
                L.append(f"        dur: {cap_dur:.1f}")
                L.append(f"        pos: {c.get('pos', 'bottom')}")
    L.append("")
    return "\n".join(L)


class Bench(ThreadingHTTPServer):
    """The bench's own server, so that a browser hanging up is quiet.

    The default handler prints a traceback for every dropped connection.
    A render takes ten or twenty seconds and a tab can be closed inside
    that window, so the default turns an ordinary event into forty lines
    of red -- which is how a working bench came to look like a crashing
    one.
    """

    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionError, OSError)):
            return
        super().handle_error(request, client_address)


def serve(project: Path, port: int = 8731, open_browser: bool = True) -> None:
    from .render import QUALITIES, render as do_render
    from .moves import choose_moves
    import time

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):            # keep the terminal quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            """Reply, unless the browser has already gone.

            A render takes ten or twenty seconds, and in that time a tab
            can be closed, reloaded, or simply give up waiting. Writing
            to that socket raises. It used to raise INSIDE the `except`
            that was trying to report the first failure, so the second
            exception escaped and printed forty lines of traceback into
            a console that is meant to be readable. A client that left
            is not an error -- there is nobody to tell.
            """
            if isinstance(body, str):
                body = body.encode("utf-8")
            try:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except (ConnectionError, OSError):
                pass

        def _file(self, path: Path, ctype):
            if not path.exists():
                return self._send(404, b"not found", "text/plain")
            self._send(200, path.read_bytes(), ctype)

        def do_GET(self):
            p = urlparse(self.path).path
            if p in ("/", "/index.html"):
                return self._send(200, PAGE, "text/html; charset=utf-8")
            if p == "/api/state":
                try:
                    return self._send(200, json.dumps(state(project)))
                except SystemExit as e:
                    return self._send(200, json.dumps({"error": str(e)}))
            if p.startswith("/thumb/"):
                name = Path(unquote(p[7:])).name          # no traversal
                return self._file(project / "analysis" / "thumbs" / name, "image/jpeg")
            if p.startswith("/out/"):
                name = Path(unquote(p[5:])).name
                return self._file(project / "out" / name, "video/mp4")
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            p = urlparse(self.path).path
            if p == "/api/save":
                n = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(n) or b"{}")
                try:
                    text = dump(project, data)
                    (project / "film.yaml").write_text(text, encoding="utf-8")
                    Film.load(project / "film.yaml")       # validate what we wrote
                    return self._send(200, json.dumps({"ok": True}))
                except SystemExit as e:
                    return self._send(200, json.dumps({"ok": False, "error": str(e)}))
                except Exception as e:
                    return self._send(200, json.dumps({"ok": False, "error": repr(e)}))
            if p.startswith("/api/render"):
                q = urlparse(self.path).query.replace("q=", "") or "peek"
                q = q if q in QUALITIES else "peek"
                try:
                    film = Film.load(project / "film.yaml")
                    choose_moves(film.shots)
                    for s in film.shots:
                        if s.kind == "video":
                            px = project / "analysis" / "proxies" / (Path(s.src).stem + ".mp4")
                            if px.exists():
                                s.src = px.relative_to(project).as_posix()
                    t0 = time.time()
                    out = project / "out" / f"{q}.mp4"
                    do_render(film, out, QUALITIES[q], quiet=True)
                    return self._send(200, json.dumps(
                        {"ok": True, "url": f"out/{q}.mp4",
                         "secs": round(time.time() - t0, 1)}))
                except Exception as e:
                    return self._send(200, json.dumps({"ok": False, "error": str(e)}))
            if p == "/api/quit":
                # Answer first, THEN stop -- shutting down from inside the
                # handler would deadlock, and the browser would sit there
                # waiting for a reply from a server that is closing.
                self._send(200, json.dumps({"ok": True}))
                threading.Thread(target=self.server.shutdown,
                                 daemon=True).start()
                return
            self._send(404, b"not found", "text/plain")

    srv = None
    for attempt in range(port, port + 12):
        try:
            srv = Bench(("127.0.0.1", attempt), H)
            port = attempt
            break
        except OSError:
            continue                    # bench already open, or port taken
    if srv is None:
        raise SystemExit(
            f"Could not open a port between {port} and {port + 11}.\n"
            f"Another bench is probably already running — check your browser."
        )

    url = f"http://127.0.0.1:{port}/"
    print(f"Editing bench: {url}")
    print('Click "Done" in the browser when you have finished -- that '
          'closes the\nbench and brings you back here.')
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            srv.server_close()
        except OSError:
            pass
    print("\nBench closed.")
