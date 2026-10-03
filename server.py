"""Clip2PR server. POST /fix streams progress as one JSON object per line."""
import json
import queue
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, Form, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

import engine
import github

app = FastAPI()
STATIC = Path(__file__).parent / "static"


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/sample")
def sample():
    return FileResponse(Path(__file__).parent / "demo" / "double-charge.mp4", media_type="video/mp4")


def run(video_path: str, repo_url: str, out: queue.Queue) -> None:
    step = lambda msg: out.put({"step": msg})
    try:
        owner, repo = engine.parse_repo(repo_url)
        step(f"Reading github.com/{owner}/{repo}")
        base, files = engine.fetch_repo(owner, repo)
        fix = engine.analyze(video_path, owner, repo, files, on_step=step)
        changed = engine.apply(files, fix)
        step(f"Found it in {', '.join(changed)}. Opening a pull request")
        url = github.open_pr(owner, repo, base, changed, fix)
        out.put({"done": {**fix.model_dump(exclude={"edits"}), "diff": engine.diff(files, changed), "pr_url": url}})
    except Exception as e:
        out.put({"error": str(e)})
    finally:
        Path(video_path).unlink(missing_ok=True)
        out.put(None)


@app.post("/fix")
async def fix(video: UploadFile, repo: str = Form(...)):
    suffix = Path(video.filename or "clip.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(await video.read())
    out: queue.Queue = queue.Queue()
    threading.Thread(target=run, args=(f.name, repo, out), daemon=True).start()

    def stream():
        while (msg := out.get()) is not None:
            yield json.dumps(msg) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")
