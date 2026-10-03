# Clip2PR

Drop in a screen recording of a bug and a GitHub repo link, and Gemini watches the video, finds the broken code and opens a pull request with the fix.

## Quickstart

```bash
git clone https://github.com/shxuryaaz/clip2pr && cd clip2pr
echo "GEMINI_API_KEY=paste-your-key-here" > .env
gh auth login   # skip if you're already logged in to GitHub CLI
uv run --env-file .env uvicorn server:app --port 8765
```

Get a free Gemini key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

## What you'll see

Open http://localhost:8765. Click **Use the demo shop** to load a sample recording of a double-charge bug in [the demo shop](https://shxuryaaz.github.io/clip2pr-demo-shop/), then **Find and fix**. Progress streams in on the right. In about 80 seconds you get Gemini's verdict (what was on screen, what it should have been, the root cause), the diff, and a link to the new pull request. The timeline under the video marks each step the user took and the moment the bug shows up; click any of them to jump there.

To use it on your own app, drop your own recording on the left and paste your repo's URL. The repo needs to be one your GitHub login can push branches to.

## Requirements

- [uv](https://docs.astral.sh/uv/) (it installs Python 3.13+ and the dependencies on first run)
- [GitHub CLI](https://cli.github.com/) logged in, or `GITHUB_TOKEN=...` in `.env`
- A Gemini API key

To record your own repro clips the way the demo was made: `uv run playwright install chromium`, then `uv run scripts/record_bug.py <url> bug.mp4` (needs ffmpeg).

## Troubleshooting

| You see | Fix |
|---|---|
| `gemini-3.8-flash is out of free quota, trying ...` | The free tier allows 20 requests a day per model. Clip2PR falls back to 3.7 and 3.5 Flash on its own. Quota resets at midnight Pacific time. |
| `No GitHub token. Set GITHUB_TOKEN or run gh auth login.` | Run `gh auth login`, or add `GITHUB_TOKEN=...` to `.env`. |
| `Gemini's edit for ... does not match the file exactly once` | Gemini proposed an edit that didn't match the real code, so nothing was committed. Run it again. |

## Project structure

- `server.py`: FastAPI app. Serves the page and streams each step of `POST /fix`.
- `engine.py`: reads the repo, sends video and code to Gemini, checks the proposed edits against the real files.
- `github.py`: creates the branch, commits the fix, opens the pull request.
- `static/index.html`: the whole UI.
- `scripts/record_bug.py`: records a repro clip with Playwright.
- `demo/double-charge.mp4`: the sample recording.
- `deck/`: builds the Hackdays 2.0 submission PDF from the official template.
- `test_engine.py`: checks that edits are applied only when they match the code exactly once.
