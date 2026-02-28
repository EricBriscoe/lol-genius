from __future__ import annotations

import logging
import os


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    import uvicorn

    host = os.environ.get("PROXY_HOST", "0.0.0.0")
    port = int(os.environ.get("PROXY_PORT", "8080"))
    uvicorn.run("lol_genius.proxy.app:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
