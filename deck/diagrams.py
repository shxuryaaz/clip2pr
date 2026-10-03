"""Render the workflow and architecture diagrams as PNGs in the template's colours."""
import base64
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
# set_content pages can't load file:// fonts, so inline them.
FONT = lambda name: "data:font/ttf;base64," + base64.b64encode((HERE / "fonts" / name).read_bytes()).decode()

BASE = f"""
@font-face {{ font-family: Plex; src: url({FONT("IBMPlexSansCondensed-Regular.ttf")}); }}
@font-face {{ font-family: Plex; font-weight: 600; src: url({FONT("IBMPlexSansCondensed-SemiBold.ttf")}); }}
@font-face {{ font-family: Plex; font-weight: 700; src: url({FONT("IBMPlexSansCondensed-Bold.ttf")}); }}
* {{ box-sizing: border-box; margin: 0; }}
body {{ width: 1444px; height: 476px; background: #f3f5fa; font-family: Plex; color: #1b2a4a;
       display: flex; flex-direction: column; justify-content: center; padding: 0 26px; }}
.row {{ display: flex; align-items: stretch; }}
.arrow {{ color: #2e86de; font-size: 34px; display: flex; align-items: center; padding: 0 8px; }}
.note {{ text-align: center; color: #5a6b8c; font-size: 20px; margin-top: 26px; }}
"""

WORKFLOW = """
<style>
.box { flex: 1; background: #fff; border: 2px solid #2e86de; border-radius: 14px; padding: 18px 16px; }
.box.ai { border-color: #e2542b; }
.n { display: inline-grid; place-items: center; width: 34px; height: 34px; border-radius: 50%;
     background: #2e86de; color: #fff; font-weight: 700; font-size: 18px; }
.ai .n { background: #e2542b; }
h3 { font-size: 23px; font-weight: 700; margin: 12px 0 6px; }
p { font-size: 18px; line-height: 1.3; color: #3c4a68; }
</style>
<div class="row">
  <div class="box"><span class="n">1</span><h3>Record</h3><p>User screen-records the bug. No written description.</p></div>
  <div class="arrow">→</div>
  <div class="box"><span class="n">2</span><h3>Submit</h3><p>Drop the clip on the page and paste the GitHub repo link.</p></div>
  <div class="arrow">→</div>
  <div class="box"><span class="n">3</span><h3>Gather</h3><p>Server pulls the repo's code and uploads the video to Gemini.</p></div>
  <div class="arrow">→</div>
  <div class="box ai"><span class="n">4</span><h3>Watch and read</h3><p>One Gemini call: user's steps, bug timestamp, root cause, fix.</p></div>
  <div class="arrow">→</div>
  <div class="box"><span class="n">5</span><h3>Check</h3><p>Each edit must match the real code exactly once, or it's refused.</p></div>
  <div class="arrow">→</div>
  <div class="box"><span class="n">6</span><h3>Pull request</h3><p>New branch, commit, and a PR with the video evidence.</p></div>
</div>
<p class="note">Every step streams to the page live. About 80 seconds end to end on the demo repo.</p>
"""

ARCH = """
<style>
.layer { flex: 1; background: #fff; border: 2px solid var(--c); border-radius: 14px; padding: 16px 18px; }
.tag { font-size: 15px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--c); }
h3 { font-size: 23px; font-weight: 700; margin: 6px 0 10px; }
ul { padding-left: 20px; font-size: 18px; line-height: 1.45; color: #3c4a68; }
code { font-family: Plex; font-weight: 600; color: #1b2a4a; }
</style>
<div class="row">
  <div class="layer" style="--c:#2e86de"><div class="tag">Client layer</div><h3>Browser page</h3>
    <ul><li>HTML, CSS, plain JS</li><li>Drop zone and repo link</li><li>Live step log</li><li>Bug tape over the video</li><li>Diff and PR link</li></ul></div>
  <div class="arrow">⇄</div>
  <div class="layer" style="--c:#e2542b"><div class="tag">Application layer</div><h3>FastAPI server</h3>
    <ul><li><code>server.py</code> streams each step</li><li><code>engine.py</code> reads the repo, calls Gemini, checks edits</li><li><code>github.py</code> opens the PR</li></ul></div>
  <div class="arrow">⇄</div>
  <div class="layer" style="--c:#f2a93b"><div class="tag">Data layer</div><h3>No database</h3>
    <ul><li>GitHub repo is the source of truth, read fresh each run</li><li>Video kept in Gemini Files for 48 hours</li></ul></div>
  <div class="arrow">⇄</div>
  <div class="layer" style="--c:#1b2a4a"><div class="tag">Infrastructure</div><h3>Cloud APIs</h3>
    <ul><li>Gemini API: 3.8 Flash, falls back to 3.7 and 3.5</li><li>GitHub REST API</li><li>Any Python host</li><li>Demo shop on GitHub Pages</li></ul></div>
</div>
"""


def render(html: str, out: Path) -> None:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1444, "height": 476}, device_scale_factor=2)
        pg.set_content(f"<style>{BASE}</style>{html}")
        pg.evaluate("document.fonts.ready.then(() => document.fonts.size)")
        pg.screenshot(path=str(out))
        b.close()


if __name__ == "__main__":
    render(WORKFLOW, HERE / "workflow.png")
    render(ARCH, HERE / "architecture.png")
    print("ok")
