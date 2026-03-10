from __future__ import annotations

import argparse

from _bootstrap import bootstrap

bootstrap()

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FastAPI backend server")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    uvicorn.run("src.api.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
