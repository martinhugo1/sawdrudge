# Live News-Homepage Mirror (branding swap)

This is a starting implementation of a server-rendered live mirror of the Drudge Report homepage, swapping the masthead and first qualifying editorial image. It fetches current source HTML on demand and caches it for 180 seconds by default. The original headline links remain outbound links to the originating publishers.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000. For a public hosting service such as Render, use `pip install -r requirements.txt` as the build command and `gunicorn app:app --bind 0.0.0.0:$PORT` as the start command.

## Customize

1. Replace `static/your-logo.png` with your own logo artwork (retaining the filename).
2. Replace `static/your-main-image.svg` with your main visual (retaining the filename).
3. Optional: set `REFRESH_SECONDS=180` (minimum 30) to adjust frequency.
4. Set the site's actual title by changing `Your News Site` in app.py.

## Limitations

- The source HTML can change at any time; image selection uses heuristics, not a guaranteed permanent selector. Inspect page after first deployment.
- The upstream website can rate-limit or reject automated fetching. This implementation does not bypass access controls, and cannot guarantee continuous delivery.
- Upstream ad scripts, tracking and interactive scripts are intentionally not mirrored; CSS and editorial links are preserved where possible.
- Editorial images may be inaccessible to third-party browsers due to hotlink restrictions.
- Ensure you have appropriate permission to republish content or mirror the site's branded design. A licensing or feed arrangement is preferable for a production site.
