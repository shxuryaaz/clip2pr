"""Watch a bug video, read the repo, return a fix. The video is the only bug report."""
import difflib
import io
import os
import re
import subprocess
import tarfile
import time

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field

# Busy models 503 now and then; on stage we fall through to the next one instead of dying.
MODELS = os.environ.get("CLIP2PR_MODELS", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash").split(",")
CODE_EXT = {".js", ".ts", ".jsx", ".tsx", ".py", ".html", ".css", ".json", ".go", ".rb",
            ".java", ".kt", ".swift", ".vue", ".svelte", ".php", ".rs", ".c", ".cpp", ".h", ".md"}
SKIP_DIRS = {"node_modules", "dist", "build", ".next", "vendor", "__pycache__", ".git"}
MAX_FILE = 100_000
# ponytail: whole repo goes in the prompt, fine for small repos. Retrieval for big ones later.
MAX_TOTAL = 800_000


def github_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok:
        tok = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    if not tok:
        raise RuntimeError("No GitHub token. Set GITHUB_TOKEN or run `gh auth login`.")
    return tok


def parse_repo(url: str) -> tuple[str, str]:
    m = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", url.strip())
    if not m:
        raise ValueError(f"Not a GitHub repo URL: {url}")
    return m[1], m[2]


def fetch_repo(owner: str, repo: str) -> tuple[str, dict[str, str]]:
    """Returns (default branch, {path: text}) for the source files worth reading."""
    h = {"Authorization": f"Bearer {github_token()}", "Accept": "application/vnd.github+json"}
    with httpx.Client(headers=h, follow_redirects=True, timeout=60) as gh:
        info = gh.get(f"https://api.github.com/repos/{owner}/{repo}")
        info.raise_for_status()
        branch = info.json()["default_branch"]
        tar = gh.get(f"https://api.github.com/repos/{owner}/{repo}/tarball/{branch}")
        tar.raise_for_status()

    files, total = {}, 0
    with tarfile.open(fileobj=io.BytesIO(tar.content), mode="r:gz") as tf:
        for m in tf.getmembers():
            path = m.name.split("/", 1)[-1]  # drop the "owner-repo-sha/" prefix
            parts = path.split("/")
            if not m.isfile() or m.size > MAX_FILE or SKIP_DIRS & set(parts[:-1]):
                continue
            if os.path.splitext(path)[1].lower() not in CODE_EXT or path.endswith("-lock.json"):
                continue
            text = tf.extractfile(m).read().decode("utf-8", "replace")
            if total + len(text) > MAX_TOTAL:
                break
            files[path] = text
            total += len(text)
    return branch, files


class Edit(BaseModel):
    path: str = Field(description="Repo-relative path of a file to change")
    find: str = Field(description="Exact snippet copied from the current file, a few whole lines, unique in that file")
    replace: str = Field(description="What those lines become")


class Fix(BaseModel):
    bug_title: str = Field(description="Short title for the bug, under 60 characters")
    steps_seen: list[str] = Field(description="What the user did in the video, step by step, with mm:ss")
    seen_at: str = Field(description="mm:ss in the video where the wrong behaviour is first visible")
    on_screen: str = Field(description="What the screen showed at seen_at, quoting numbers or text exactly")
    expected: str = Field(description="What should have been on screen instead, with the correct values")
    root_cause: str = Field(description="Which code causes it and why, naming file, function and line")
    edits: list[Edit] = Field(description="Smallest set of file changes that fixes the bug")
    pr_title: str
    model: str = Field(default="", description="Leave empty")


PROMPT = """You are a senior engineer fixing a bug. The video is a screen recording from a user.
They typed no description; the recording is the whole bug report.

1. Watch the video closely. List what the user does, with timestamps.
2. Find the moment the app does something wrong. Read numbers and text off the screen exactly,
   then work out what the correct values should have been.
3. Read the repository below and find the code that produces exactly that wrong behaviour.
   Ignore code that merely looks odd but does not cause what the video shows.
4. Make the smallest fix as find/replace edits. Each `find` is copied character-for-character
   from the file (whole lines, indentation included) and appears exactly once in it.

Repository {owner}/{repo}:
{code}"""


def analyze(video_path: str, owner: str, repo: str, files: dict[str, str], on_step=print) -> Fix:
    # No timeout by default, and the SDK retries silently; we want fast failure and our own fallback.
    client = genai.Client(http_options=types.HttpOptions(timeout=150_000, retry_options=types.HttpRetryOptions(attempts=1)))
    on_step("Uploading the recording to Gemini")
    video = client.files.upload(file=video_path)
    while video.state.name == "PROCESSING":
        time.sleep(1)
        video = client.files.get(name=video.name)
    if video.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini could not process the video ({video.state.name})")

    code = "\n\n".join(f"===== {p} =====\n{t}" for p, t in files.items())
    on_step(f"Gemini is watching the video and reading {len(files)} files")
    config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=Fix)
    tries = [(m, wait) for wait in (0, 5, 15) for m in MODELS]
    for i, (model, wait) in enumerate(tries):
        time.sleep(wait if model == MODELS[0] else 0)
        try:
            resp = client.models.generate_content(
                model=model, contents=[video, PROMPT.format(owner=owner, repo=repo, code=code)], config=config)
            break
        except (errors.APIError, httpx.HTTPError) as e:
            busy = isinstance(e, httpx.HTTPError) or e.code in (429, 500, 503, 504)
            if not busy or i == len(tries) - 1:
                raise
            on_step(f"{model} is busy, trying {tries[i + 1][0]}")
    fix: Fix = resp.parsed
    if not fix.edits:
        raise RuntimeError("Gemini found no code change to make")
    fix.model = model
    return fix


def apply(files: dict[str, str], fix: Fix) -> dict[str, str]:
    """New contents of every changed file. Refuses edits that don't match the real code."""
    out = {}
    for e in fix.edits:
        text = out.get(e.path, files.get(e.path))
        if text is None:
            raise RuntimeError(f"Gemini wanted to edit {e.path}, which is not in the repo")
        if text.count(e.find) != 1:
            raise RuntimeError(f"Gemini's edit for {e.path} does not match the file exactly once")
        out[e.path] = text.replace(e.find, e.replace)
    return out


def diff(files: dict[str, str], changed: dict[str, str]) -> str:
    out = []
    for path, new in changed.items():
        out += difflib.unified_diff(files[path].splitlines(keepends=True), new.splitlines(keepends=True),
                                    f"a/{path}", f"b/{path}")
    return "".join(out)


if __name__ == "__main__":
    import sys

    owner, repo = parse_repo(sys.argv[2])
    _, files = fetch_repo(owner, repo)
    fix = analyze(sys.argv[1], owner, repo, files)
    print(fix.model_dump_json(indent=2, exclude={"edits"}))
    print(diff(files, apply(files, fix)))
