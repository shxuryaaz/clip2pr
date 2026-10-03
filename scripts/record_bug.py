"""Record the demo shop bug as a video, the way a user would.

uv run scripts/record_bug.py <shop url or path> <out.mp4>
"""
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# Headless video has no mouse pointer, so draw one and flash a ring on every click.
CURSOR_JS = """
const c = document.createElement('div');
c.style.cssText = 'position:fixed;z-index:99999;width:22px;height:22px;pointer-events:none;'
  + 'left:-50px;top:-50px;transition:left .45s ease, top .45s ease;';
c.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M3 2l7 19 2.5-7.5L20 11z" fill="#000" stroke="#fff" stroke-width="1.5"/></svg>';
document.addEventListener('DOMContentLoaded', () => document.body.appendChild(c));
window.__moveCursor = (x, y) => { c.style.left = x + 'px'; c.style.top = y + 'px'; };
window.__ring = (x, y) => {
  const r = document.createElement('div');
  r.style.cssText = `position:fixed;z-index:99998;left:${x-18}px;top:${y-18}px;width:36px;height:36px;`
    + 'border-radius:50%;border:3px solid #e8572a;pointer-events:none;transition:all .5s;';
  document.body.appendChild(r);
  requestAnimationFrame(() => { r.style.transform = 'scale(1.8)'; r.style.opacity = '0'; });
  setTimeout(() => r.remove(), 600);
};
"""


def main(url: str, out: str) -> None:
    if not url.startswith("http"):
        url = Path(url).resolve().as_uri()
    tmp = Path(out).parent / "_rec"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720},
                                  record_video_dir=str(tmp),
                                  record_video_size={"width": 1280, "height": 720})
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        page.goto(url)
        page.wait_for_timeout(1500)

        def click(selector: str, pause: int = 1600) -> None:
            box = page.locator(selector).bounding_box()
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            page.evaluate(f"__moveCursor({x}, {y})")
            page.wait_for_timeout(600)
            page.evaluate(f"__ring({x}, {y})")
            page.click(selector)
            page.wait_for_timeout(pause)

        click('button[data-id="hoodie"]')
        click("#pay", 2500)
        click('button[data-id="stickers"]', 2000)  # one more thing after paying
        click("#pay", 3000)  # and gets charged again

        video = page.video
        ctx.close()
        browser.close()
        # Playwright's webm has no duration, so browsers can't seek it. mp4 plays everywhere.
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video.path(), "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
