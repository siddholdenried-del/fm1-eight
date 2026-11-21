#!/usr/bin/env python3
"""ghettomachine.bongcult.com: BongTech GhettoMachine's page (docs/how-it-works.html) with the emulator framed in it, and the emulator.

  python3 -I site/build.py site/public   (from the repository's top, after tools/build.py ../../app --web in third_party/fm1-base;
                                         site/publish.sh does this, commits it and pushes)

  python3 -I site/build.py --landing-only site/public   (refresh the page and branding only)

site/public/index.html   the page, a whole HTML document, its "Play it" section framing emu/
site/public/emu/         the emulator: app/build/emu (the page, app.wasm, the audio worklet, its parts)
site/public/_headers     the headers Cloudflare serves with it (wasm's type, caching)
"""
import html
import json
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
GUIDE = (
    ("", "Quick start", "Quick start"),
    ("beats", "Drums & steps", "Drums and sequencing"),
    ("sounds", "Sounds & samples", "Synths, samples and acid"),
    ("recording", "Recording", "Recording"),
    ("performance", "Live & song", "Playing live"),
    ("mixer", "Mixer & FX", "Mixer and effects"),
    ("setup", "Save & install", "Saving and installing"),
)
MASTHEAD = """<a class="bc-skip" href="#gm-main">Skip to content</a>
<header class="bc-masthead">
  <div class="bc-stars" aria-hidden="true"><span>+</span><span>+</span><span>·</span><span>+</span><span>+</span><span>·</span></div>
  <p class="bc-badge">BongTech · Project site</p>
  <a class="bc-name" href="https://bongcult.com/"><img src="/bong-cult-logo.svg" alt="Bong Cult home" width="866" height="320"></a>
  <div class="bc-rainbow" aria-hidden="true"></div>
</header>
"""
LANDING = """<div class="hero gm-home">
  <div class="screen">
    <div class="top"><span class="label">Firmware for the M-VAVE FM-1</span><span class="ver">V0.4</span></div>
    <h1><span class="logo">GhettoMachine</span></h1>
    <p class="sub">Four-track groovebox firmware. A 909 or 808, three synth or sampler tracks, and a 64-step sequencer.</p>
  </div>
  <p class="lede">Make a beat in the browser or look up the controls for the FM-1.</p>
  <div class="gm-actions" id="play">
    <a class="gm-button gm-primary" href="/guide/">Open the User Guide</a>
    <a class="gm-button" href="/emu/">Play in browser</a>
  </div>
  <p class="gm-home-links"><a href="/technical/">How it works</a> · <a href="REPO">Source on GitHub</a></p>
  <details class="gm-technical-topics">
    <summary>Technical topics</summary>
    TECHNICAL_TOPIC_LINKS
  </details>
</div>
"""


def guide_path(slug):
    return f"/guide/{slug}/" if slug else "/guide/"


def nav_link(href, label, current):
    selected = ' aria-current="page"' if href == current else ''
    return f'<a href="{href}"{selected}>{html.escape(label)}</a>'


def render_document(head, title, path, content, guide_slug=None):
    nav = [("/", "Home"), ("/guide/", "User Guide"), ("/emu/", "Play"), ("/technical/", "How it works")]
    is_guide = guide_slug is not None
    if is_guide:
        nav = [("/", "Home"), ("/emu/", "Play in browser")]
    site_nav = "".join(nav_link(href, label, path) for href, label in nav)
    guide_nav = ''.join(nav_link(guide_path(slug), label, path) for slug, label, _ in GUIDE)
    chapters = (f'<nav class="gm-chapters" aria-label="Guide chapters">{guide_nav}</nav>' if is_guide else '')
    css_class = ' gm-guide-page' if is_guide else ''
    js = '<script src="/chapter-redirect.js"></script>\n' if path == '/' else ''
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="theme-color" content="#8500ff">\n'
        '<meta name="description" content="BongTech GhettoMachine, a four-track groovebox firmware for the M-VAVE FM-1, playable in the browser.">\n'
        f'<link rel="canonical" href="https://ghettomachine.bongcult.com{path}">\n'
        + re.sub(r'<title>[^<]*</title>', f'<title>{html.escape(title)}</title>', head, count=1) + '\n'
        + ICON.replace("HREF", "/favicon.svg")
        + '<link rel="stylesheet" href="/bong-cult-shell.css">\n' + js + '</head>\n'
        + f'<body class="gm-bong-cult{css_class}">\n' + MASTHEAD
        + '<div class="bc-frame">\n<aside class="bc-sidebar"><div class="gm-nav-stack">'
        + f'<nav aria-label="GhettoMachine">{site_nav}</nav>{chapters}</div></aside>\n'
        + f'<main class="wrap" id="gm-main" tabindex="-1">\n{content}\n</main>\n</div>\n</body>\n</html>\n'
    )


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
        '    <div class="emu-frame"><iframe src="/emu/" title="GhettoMachine, running in the browser" allow="midi; autoplay" '
        'loading="lazy"></iframe></div>\n'
        f'    <p><a href="/emu/">Open it full size</a> · <a href="{REPO}">The source</a> · '
        f'<a href="{REPO}/blob/main/MANUAL.md">The manual</a></p>\n'
        "  </section>")
    page, n = re.subn(r"<!-- emu:start -->.*?<!-- emu:end -->", frame, page, flags=re.S)
    if n != 1:
        raise SystemExit("site: the page has no <!-- emu:start --> ... <!-- emu:end --> block")
    page = page.replace("It's about 430 KB of code, and the same code runs in your browser, right below.",
                        "It's about 430 KB of code, and the same code runs in your browser, right here.")
    page = re.sub(r'<meta name="claude:[^>]*>\n', "", page)
    head_end = page.index("</style>") + len("</style>")
    head = page[:head_end]
    tag = '<div class="wrap">'
    contents = page[head_end:].strip()
    if not contents.startswith(tag) or not contents.endswith("</div>"):
        raise SystemExit("site: could not find the landing page wrapper")
    contents = contents[len(tag):-len("</div>")].strip()
    # Keep previously shared /#chapter addresses working. The labeled links
    # on the home page cover the same destinations even with JS disabled.
    links = re.findall(r'<li><a href="#([a-z]+)"><i[^>]*></i>([^<]+)</a></li>', contents)
    if not links or len(links) != len(set(slug for slug, _ in links)):
        raise SystemExit("site: could not identify original technical anchors")
    fallback = "<ul>" + "".join(f'<li><a href="/technical/#{slug}">{label}</a></li>' for slug, label in links) + "</ul>"
    (out / "chapter-redirect.js").write_text(
        "'use strict';\n"
        "(() => {\n"
        f"  const chapters = new Set({json.dumps([slug for slug, _ in links])});\n"
        "  const forward = () => {\n"
        "    const chapter = location.hash.slice(1);\n"
        "    if (chapters.has(chapter)) location.replace('/technical/' + location.search + location.hash);\n"
        "  };\n"
        "  forward();\n"
        "  addEventListener('hashchange', forward);\n"
        "})();\n"
    )
    landing = LANDING.replace("REPO", REPO).replace("TECHNICAL_TOPIC_LINKS", fallback)
    (out / "index.html").write_text(render_document(head, "GhettoMachine · BongTech", "/", landing))
    tech_dir = out / "technical"
    tech_dir.mkdir(exist_ok=True)
    (tech_dir / "index.html").write_text(render_document(head, "Inside GhettoMachine · Technical tour", "/technical/", contents))
    for i, (slug, label, title) in enumerate(GUIDE):
        path = guide_path(slug)
        dest = out / path.strip("/")
        dest.mkdir(parents=True, exist_ok=True)
        chapter = (ROOT / "site" / "guide" / f"{slug or 'index'}.html").read_text().strip()
        nav = []
        if i:
            prev_slug, prev_label, _ = GUIDE[i - 1]
            nav.append(f'<a rel="prev" href="{guide_path(prev_slug)}">← {html.escape(prev_label)}</a>')
        if i < len(GUIDE) - 1:
            next_slug, next_label, _ = GUIDE[i + 1]
            nav.append(f'<a rel="next" href="{guide_path(next_slug)}">{html.escape(next_label)} →</a>')
        body = (
            '<article class="gm-guide">'
            f'<p class="gm-crumb">User Guide · {i + 1} of {len(GUIDE)}</p><h1>{html.escape(title)}</h1>\n'
            + chapter + '<nav class="gm-guide-pager" aria-label="Adjacent chapters">'
            + "".join(nav) + '</nav></article>'
        )
        (dest / "index.html").write_text(render_document(head, f"{title} · GhettoMachine User Guide", path, body, slug))
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
