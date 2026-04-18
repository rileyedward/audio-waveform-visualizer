from __future__ import annotations

import argparse
import threading
import time
import webbrowser

import uvicorn


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="visualizer-ui", description="Launch the visualizer web UI.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    p.add_argument("--reload", action="store_true", help="Dev: enable uvicorn auto-reload")
    args = p.parse_args(argv)

    url = f"http://{args.host}:{args.port}"
    print(f"visualizer-ui: serving at {url}")

    if not args.no_browser:
        def _open() -> None:
            time.sleep(0.8)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(
        "visualizer.ui.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
