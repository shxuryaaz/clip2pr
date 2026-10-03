"""Open a pull request with Gemini's fix. Uses the REST API, no clone."""
import base64
import re
import time

import httpx

from engine import Fix, github_token


def pr_body(fix: Fix) -> str:
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(fix.steps_seen, 1))
    return f"""## {fix.bug_title}

Found from a screen recording by [Clip2PR](https://github.com/shxuryaaz/clip2pr). Nobody typed a bug report.

**What the user did**
{steps}

**What went wrong (at {fix.seen_at} in the video)**
{fix.on_screen}

**What should have happened**
{fix.expected}

**Root cause**
{fix.root_cause}

Model: `{fix.model}`
"""


def open_pr(owner: str, repo: str, base: str, changed: dict[str, str], fix: Fix) -> str:
    api = f"https://api.github.com/repos/{owner}/{repo}"
    h = {"Authorization": f"Bearer {github_token()}", "Accept": "application/vnd.github+json"}
    slug = re.sub(r"[^a-z0-9]+", "-", fix.bug_title.lower()).strip("-")[:40]
    branch = f"clip2pr/{slug}-{int(time.time()) % 100000}"

    with httpx.Client(headers=h, timeout=30) as gh:
        sha = gh.get(f"{api}/git/ref/heads/{base}").raise_for_status().json()["object"]["sha"]
        gh.post(f"{api}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": sha}).raise_for_status()
        for path, text in changed.items():
            cur = gh.get(f"{api}/contents/{path}", params={"ref": branch}).raise_for_status().json()
            gh.put(f"{api}/contents/{path}", json={
                "message": f"{fix.pr_title}\n\nFound by Clip2PR from a screen recording.",
                "content": base64.b64encode(text.encode()).decode(),
                "sha": cur["sha"],
                "branch": branch,
            }).raise_for_status()
        pr = gh.post(f"{api}/pulls", json={"title": fix.pr_title, "head": branch, "base": base,
                                            "body": pr_body(fix)}).raise_for_status().json()
    return pr["html_url"]
