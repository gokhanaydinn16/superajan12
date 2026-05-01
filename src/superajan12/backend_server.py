from __future__ import annotations

import argparse

import uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="superajan12-backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", default="info")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    uvicorn.run(
        "superajan12.backend_api:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
