#!/usr/bin/env python3
"""ghettomachine.bongcult.com: BongTech GhettoMachine's page (docs/how-it-works.html) with the emulator framed in it, and the emulator.

  python3 -I site/build.py site/public   (from the repository's top, after tools/build.py ../../app --web in third_party/fm1-base;
                                         site/publish.sh does this, commits it and pushes)

  python3 -I site/build.py --landing-only site/public   (refresh the page and branding only)

site/public/index.html   the page, a whole HTML document, its "Play it" section framing emu/
site/public/emu/         the emulator: app/build/emu (the page, app.wasm, the audio worklet, its parts)
site/public/_headers     the headers Cloudflare serves with it (wasm's type, caching)
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/siddholdenried-del/ghettomachine"
ICON = '<link rel="icon" href="HREF" type="image/svg+xml">\n'
# the emulator's sound on phones: Safari mutes web audio while an iPhone is in silent mode unless the page asks for
# the "playback" audio session (the Audio Session API, where there is one), and a call, Siri or another app leaves the
# context "interrupted" until something resumes it. Before the page's own script, so the session is set before the
# switch-on makes its AudioContext; every AudioContext it makes is kept, and woken by the next touch or key.
AUDIO_FIX = """<script>
(function () {
  try { if (navigator.audioSession) navigator.audioSession.type = "playback"; } catch (e) {}
  var A = window.AudioContext;
  if (!A) return;
  var made = [];
  window.AudioContext = class extends A { constructor(o) { super(o); made.push(this); } };
  function wake() {
    made.forEach(function (c) { if (c.state !== "running" && c.state !== "closed") c.resume().catch(function () {}); });
  }
  ["pointerdown", "touchend", "keydown"].forEach(function (t) { document.addEventListener(t, wake, true); });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) wake(); });
})();
</script>
"""
START = '<div class="start" id="start"><button type="button" id="go">Switch on</button></div>'
START_HINT = ('<div class="start" id="start"><div class="startbox"><button type="button" id="go">Switch on</button>'
              '<p class="hint">Then press PLAY / STOP to hear the demo groove.</p></div></div>')

FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#5AD282"/>'
           '<text x="32" y="47" font-family="Arial Narrow, Arial, sans-serif" font-weight="700" font-size="44" '
           'text-anchor="middle" fill="#16171B">8</text></svg>\n')


BRANDING = ROOT / "site" / "branding"
SHELL_START = """<a class="bc-skip" href="#gm-main">Skip to the guide</a>
<header class="bc-masthead">
  <div class="bc-stars" aria-hidden="true"><span>+</span><span>+</span><span>·</span><span>+</span><span>+</span><span>·</span></div>
  <p class="bc-badge">BongTech · Project site</p>
  <a class="bc-name" href="https://bongcult.com/"><img src="bong-cult-logo.svg" alt="Bong Cult home" width="866" height="320"></a>
  <div class="bc-rainbow" aria-hidden="true"></div>
</header>
<div class="bc-frame">
  <aside class="bc-sidebar">
    <nav aria-label="GhettoMachine">
      <a href="#play">Play it</a>
      <a href="#platform">Read the guide</a>
      <a href="#story">Project history</a>
      <a href="https://bongcult.com/">Bong Cult journal</a>
    </nav>
  </aside>
  <main class="wrap" id="gm-main" tabindex="-1">
"""


def build_landing(out):
    out.mkdir(parents=True, exist_ok=True)
    page = (ROOT / "docs" / "how-it-works.html").read_text()
    frame = (
        '<section id="play" style="--c: var(--t2)">\n'
        '    <div class="band"><h2>Play it</h2><span class="tag">IN THE BROWSER</span></div>\n'
        "    <p>This is GhettoMachine itself, compiled to WebAssembly: the same sequencer, drums, synth, effects and screen as on "
        "the FM-1, drawn as its panel. Press <strong>Switch on</strong>, then <strong>PLAY / STOP</strong> to hear its demo "
        "groove, and play it with the mouse or your computer's keyboard. Your work is kept in this browser. If an iPhone "
        "stays silent, turn up its volume, and turn off silent mode: older iOS versions mute web audio in it.</p>\n"
        '    <div class="emu-frame"><iframe src="emu/" title="GhettoMachine, running in the browser" allow="midi; autoplay" '
        'loading="lazy"></iframe></div>\n'
        f'    <p><a href="emu/">Open it full size</a> · <a href="{REPO}">The source</a> · '
        f'<a href="{REPO}/blob/main/MANUAL.md">The manual</a></p>\n'
        "  </section>")
    page, n = re.subn(r"<!-- emu:start -->.*?<!-- emu:end -->", frame, page, flags=re.S)
    if n != 1:
        raise SystemExit("site: the page has no <!-- emu:start --> ... <!-- emu:end --> block")
    page = page.replace("It's about 430 KB of code, and the same code runs in your browser, right below.",
                        "It's about 430 KB of code, and the same code runs in your browser, right here.")
    page = re.sub(r'<meta name="claude:[^>]*>\n', "", page)
    head_end = page.index("</style>") + len("</style>")
    tag = '<div class="wrap">'
    contents = page[head_end:].strip()
    if not contents.startswith(tag) or not contents.endswith("</div>"):
        raise SystemExit("site: could not find the landing page wrapper")
    contents = contents[len(tag):-len("</div>")].strip()
    doc = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="theme-color" content="#8500ff">\n'
        '<meta name="description" content="BongTech GhettoMachine, a four-track groovebox firmware for the M-VAVE FM-1: how it '
        'works, and the firmware itself running in the browser.">\n'
        + page[:head_end] + '\n'
        + ICON.replace("HREF", "favicon.svg")
        + '<link rel="stylesheet" href="bong-cult-shell.css">\n</head>\n<body class="gm-bong-cult">\n'
        + SHELL_START + contents + '\n  </main>\n</div>\n</body>\n</html>\n'
    )
    (out / "index.html").write_text(doc)
    for file in ("bong-cult-logo.svg", "bong-cult-shell.css"):
        shutil.copyfile(BRANDING / file, out / file)


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--landing-only":
        build_landing(Path(args[1]).resolve())
        return
    if len(args) != 1 or args[0].startswith("-"):
        raise SystemExit(__doc__)
    out = Path(args[0]).resolve()
    emu_src = ROOT / "app" / "build" / "emu"
    if not (emu_src / "app.wasm").exists():
        raise SystemExit("site: no app/build/emu/app.wasm (tools/build.py ../../app --web first)")
    if out.exists():
        shutil.rmtree(out)
    (out / "emu").mkdir(parents=True)
    build_landing(out)

    for f in ("index.html", "app.js", "app.wasm", "app_worklet.js", "worklet.js"):
        shutil.copy(emu_src / f, out / "emu" / f)
    shutil.copytree(emu_src / "parts", out / "emu" / "parts")
    emu_page = (out / "emu" / "index.html").read_text()
    emu_page, n1 = re.subn(r"<title>[^<]*</title>", "<title>BongTech GhettoMachine in the browser</title>", emu_page, count=1)
    emu_page, n2 = re.subn(r"<h1>[^<]*</h1>", '<h1>GhettoMachine</h1>\n  <p><a href="../">How it works</a></p>', emu_page, count=1)
    if n1 != 1 or n2 != 1 or emu_page.count(START) != 1:
        raise SystemExit("site: the emulator's page has no <title>, <h1> or switch-on block to change")
    emu_page = emu_page.replace(START, START_HINT)
    # framed in the page: no title of its own (the page has it), less room around it
    emu_page = emu_page.replace("</head>", ICON.replace("HREF", "../favicon.svg") + AUDIO_FIX +
                                '<script>if (self !== top) document.documentElement.classList.add("framed");</script>\n'
                                "<style>.framed body > header { display: none; } "
                                ".framed body { padding-block: 14px 14px; }\n"
                                # the name in the logo's face (the boot screen's, Sedgwick Ave Display, SIL OFL 1.1)
                                'body > header h1 { font: 400 2.4rem/1.05 "Sedgwick Ave Display", "Marker Felt", '
                                'cursive; }\n'
                                '.startbox { display: grid; justify-items: center; gap: .7rem; padding: 0 1rem; } '
                                '.start .hint { margin: 0; text-align: center; color: #fff; '
                                'font: 600 1.05rem/1.3 "Barlow Semi Condensed", "Barlow", sans-serif; '
                                'text-shadow: 0 1px 3px rgba(0, 0, 0, .8); }</style>\n'
                                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
                                'family=Sedgwick+Ave+Display&display=swap">\n</head>', 1)
    (out / "emu" / "index.html").write_text(emu_page)
    (out / "favicon.svg").write_text(FAVICON)

    (out / "_headers").write_text("/emu/*.wasm\n  Content-Type: application/wasm\n  Cache-Control: public, max-age=3600\n")
    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"site: {out} ({total // 1024} KB)")


if __name__ == "__main__":
    main()
