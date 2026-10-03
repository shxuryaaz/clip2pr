"""Fill the official Hackdays 2.0 template with Clip2PR's content.

uv run --with pymupdf deck/build.py
Keeps the template's logos, cards and headers; swaps the prompt text for ours.
"""
from pathlib import Path

import pymupdf

HERE = Path(__file__).parent
TEAM = "Clip2PR"  # must match the team name on Unstop exactly
MEMBERS = ["Shaurya Singh"]
TRACKS = [("AI / ML", "#f2a93b"), ("Open Innovation", "#2e86de")]

NAVY, GRAY, LABEL = "#1b2a4a", "#8a93a6", "#5a6b8c"
ARCH = pymupdf.Archive(str(HERE / "fonts"))
CSS = f"""
@font-face {{ font-family: Plex; src: url(IBMPlexSansCondensed-Regular.ttf); }}
@font-face {{ font-family: Plex; font-weight: bold; src: url(IBMPlexSansCondensed-SemiBold.ttf); }}
@font-face {{ font-family: Open; src: url(OpenSans.ttf); }}
* {{ font-family: Plex; color: {NAVY}; margin: 0; padding: 0; }}
ul {{ margin: 0; padding-left: 12px; }}
li {{ margin-bottom: 6px; }}
a {{ color: #2e86de; text-decoration: none; }}
"""


CARD = (243 / 255, 245 / 255, 250 / 255)


def redact(page, *texts, exact=(), below=0, cover=()):
    """Remove spans that start with any of `texts` (or equal one of `exact`, under y=`below`). Card art stays.
    Type3 glyphs in `cover` survive redaction, so they get painted over in the card colour instead."""
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = s["text"].strip()
                if t in cover:
                    # Type3 bboxes sit above the drawn glyph; pad downwards to catch it.
                    page.draw_rect(pymupdf.Rect(s["bbox"]) + (-2, -2, 2, 12), color=None, fill=CARD)
                elif t and (t.startswith(texts) or (t in exact and s["bbox"][1] >= below)):
                    page.add_redact_annot(s["bbox"], fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)


def box(page, rect, html, size=10.5, color=NAVY, align="left", font="Plex"):
    css = CSS + f"body {{ font-size: {size}px; line-height: 1.3; text-align: {align}; }} * {{ color: {color}; font-family: {font}; }} a {{ color: #2e86de; }}"
    spare, scale = page.insert_htmlbox(pymupdf.Rect(rect), html, css=css, archive=ARCH, scale_low=1)
    if spare < 0:
        raise SystemExit(f"Text does not fit on page {page.number + 1}: {html[:60]}")


def title_slide(p):
    redact(p, "[ Your Team Name", "[ Enter Your Project", "[ Member", "[Member", "Delete tracks", "Team Name",
           below=400, exact=("·", "Healthcare", "AI / ML", "Web3 Development", "Sustainability", "IoT",
                  "Open Innovation"))
    box(p, (36, 270, 585, 312), "Clip2PR: Record the Bug, Get the Fix", size=26, font="Open")
    box(p, (36, 337, 400, 351), "Team Name", size=10, color=LABEL)
    box(p, (36, 352, 560, 374), TEAM, size=14.9)
    box(p, (36, 412, 580, 434), " &nbsp;·&nbsp; ".join(MEMBERS), size=12.4)
    # The pills are one image; cover it and redraw only the tracks we're in.
    p.draw_rect((28, 456, 556, 494), color=None, fill=(1, 1, 1))
    x = 36
    for name, hexc in TRACKS:
        w = 18 + len(name) * 5.2
        rgb = tuple(int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
        p.draw_rect((x, 462, x + w, 488), color=rgb, width=1.2, radius=0.5)
        box(p, (x, 469, x + w, 484), name, size=8.6, color=hexc, align="center")
        x += w + 10


def problem_slide(p):
    redact(p, "Who is", "What's broken", "Back it up", "Why does", "What exactly", "How does",
           "What's the", "Tip:", cover=("▪",))
    problem = """<ul>
<li>Users report bugs as a screen recording and "it's broken". No steps, no logs.</li>
<li>A developer rewatches it, reproduces it, then hunts through the code by hand.</li>
<li>Developers spend about <b>50% of their programming time</b> finding and fixing bugs.¹</li>
<li>AI coding tools need a written bug report, and users never write one.</li></ul>"""
    solution = """<ul>
<li><b>Clip2PR turns a screen recording into a pull request.</b></li>
<li>Gemini watches the clip, reads the repo, and finds the code behind what's on screen.</li>
<li>The video picks the bug: on our demo repo, code-only AI blamed the wrong bug 4 out of 4 times. Clip2PR fixed the one the user hit.</li>
<li>Drop a clip, paste a repo link, get a PR with timestamped evidence in about 80 seconds.</li></ul>"""
    box(p, (50, 270, 352, 468), problem, size=10.5)
    box(p, (396, 270, 698, 468), solution, size=10.5)
    box(p, (30, 484, 600, 497), "¹ Cambridge Judge Business School research for Undo, 2013.", size=8.6, color=GRAY)


def stack_slide(p):
    redact(p, "Frameworks /", "Third-party", "Replace each", "Models,", "Server,", "Where and", "Hosting,")
    cards = {
        (45, 252, 262, 306): "HTML, CSS and plain JavaScript. Live progress streamed from the server, plus a clickable bug timeline over the video.",
        (294, 252, 511, 306): "Python 3.13+, FastAPI and Uvicorn. Streams every step to the browser as newline-delimited JSON.",
        (542, 252, 760, 306): "None needed. Code is read fresh from GitHub each run. The video sits in Gemini's file store for 48 hours.",
        (45, 358, 262, 412): "<b>Gemini API</b> watches the video and writes the fix. <b>Gemini Files API</b> takes the upload. <b>GitHub REST API</b> reads the repo and opens the PR.",
        (294, 358, 511, 412): "Gemini 3.8 Flash with structured JSON output. Falls back to 3.7 and 3.5 Flash when busy. About 3,700 tokens per fix.",
        (542, 358, 760, 412): "Playwright records repro clips, ffmpeg encodes them, uv runs Python, GitHub Pages hosts the demo shop.",
    }
    for rect, text in cards.items():
        box(p, rect, text, size=9.2)
    box(p, (30, 423, 600, 436), "Code: github.com/shxuryaaz/clip2pr", size=8.6, color=GRAY)


def diagram_slide(p, png, *texts, exact=()):
    redact(p, *texts, exact=exact)
    p.insert_image((32, 212, 758, 456), filename=str(HERE / png))


def usp_slide(p):
    redact(p, "The one thing", "way yours", "The measurable", "the end user", "What makes", "hard to copy", "Be specific")
    cards = [
        ((40, 323, 248, 452), "A screen recording is the whole bug report. Jam.dev records bugs and suggests fixes, then stops. <b>Clip2PR opens the pull request.</b>"),
        ((285, 323, 494, 452), "It fixes the bug the user actually hit. On our demo repo, code-only AI blamed the wrong bug <b>4 out of 4 times</b>. Clip2PR went straight to the one in the video."),
        ((530, 323, 739, 452), "Every edit is checked against the real code before it's committed, and every PR carries the evidence: steps, timestamp, expected vs actual. Works on any GitHub repo."),
    ]
    for rect, text in cards:
        box(p, rect, text, size=10, align="center")
    box(p, (30, 465, 700, 478), "Test repo: github.com/shxuryaaz/clip2pr-demo-shop, a shop with three real bugs and one recording of the double charge.", size=8.6, color=GRAY)


def feasibility_slide(p):
    redact(p, "Is there real", "What's already", "What's the realistic", "Judges weigh")
    rows = [
        ((95, 255, 752, 287), "<b>Working today:</b> video in, pull request out in about 80 seconds on Gemini's free tier (PR #3 on the demo repo). "
                              "<b>Next:</b> replay the clip in a real browser after the fix to prove it's gone, and search big repos instead of reading them whole."),
        ((95, 336, 752, 368), "Every team that gets bug reports from users, testers or support. Bug-recording tools like Jam.dev already built the habit, "
                              "and AI testing startups raised big in 2025 and 2026 (QA Wolf $56M, Momentic $18.7M)."),
        ((95, 417, 752, 449), "<b>October:</b> browser re-check and a Chrome extension recorder. <b>Next:</b> a GitHub App, plus Jira and Linear intake. "
                              "<b>Cost:</b> one Gemini Flash call per fix, about 3,700 tokens. The free tier covers a pilot."),
    ]
    for rect, text in rows:
        box(p, rect, text, size=9.8)
    box(p, (30, 463, 700, 476), "Funding figures: company announcements, as listed by codenote.net, 2026.", size=8.6, color=GRAY)


def prototype_slide(p):
    redact(p, "User Action", "Frontend", "Backend / API", "Processing", "Output", "[ Paste", "Show the step",
           "Replace this", "WORKFLOW", "04 / 08", exact=("→", "03"))
    box(p, (30, 166, 60, 190), "07", size=13.2, color="#ffffff", align="center")
    box(p, (68, 160, 500, 190), "WORKING PROTOTYPE", size=21.5, font="Open")
    box(p, (30, 498, 90, 512), "08 / 08", size=8.3, color=GRAY)
    p.draw_rect((30, 210, 760, 458), color=None, fill=CARD)  # hide the template's empty flow boxes
    p.insert_image((36, 214, 414, 452), filename=str(HERE / "ui.png"))
    box(p, (432, 222, 752, 452), """
<p style="font-family: Open; font-size: 14px; margin-bottom: 8px;">Video in, pull request out</p>
<ul>
<li><b>Live demo shop</b> (bug included):<br><a style="color: #2e86de; text-decoration: none;" href="https://shxuryaaz.github.io/clip2pr-demo-shop/">shxuryaaz.github.io/clip2pr-demo-shop</a></li>
<li><b>Code:</b> <a style="color: #2e86de; text-decoration: none;" href="https://github.com/shxuryaaz/clip2pr">github.com/shxuryaaz/clip2pr</a></li>
<li><b>A PR Clip2PR opened from the recording:</b><br><a style="color: #2e86de; text-decoration: none;" href="https://github.com/shxuryaaz/clip2pr-demo-shop/pull/3">github.com/shxuryaaz/clip2pr-demo-shop/pull/3</a></li>
<li>Same repo, no video: Gemini blamed the coupon code 4 out of 4 times. With the video it fixed the double charge the user actually hit.</li>
</ul>""", size=10)


def main():
    doc = pymupdf.open(HERE / "template.pdf")
    doc.fullcopy_page(3)  # becomes the prototype slide
    title_slide(doc[0])
    problem_slide(doc[1])
    stack_slide(doc[2])
    diagram_slide(doc[3], "workflow.png", "User Action", "Frontend", "Backend / API", "Processing", "Output",
                  "[ Paste", "Show the step", "Replace this", exact=("→",))
    diagram_slide(doc[4], "architecture.png", "Client Layer", "Application Layer", "Data Layer", "frastructure",
                  "[ Paste", "Show the components", "A clean box", exact=("In",))
    usp_slide(doc[5])
    feasibility_slide(doc[6])
    prototype_slide(doc[8])
    doc.delete_page(7)  # "To Be Kept In Mind" rules slide
    out = HERE / "Clip2PR-Hackdays2.pdf"
    doc.save(out, garbage=4, deflate=True)
    print(out, doc.page_count, "pages")


if __name__ == "__main__":
    main()
