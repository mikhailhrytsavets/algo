"""Entry point: loads settings and starts manager."""
from __future__ import annotations

import asyncio
import logging
import pathlib
import sys
from typing import Any, Dict

import tomllib

from app.manager import EngineManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

CONFIG_FILE = pathlib.Path("settings.toml")


def load_settings() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        logging.error("settings.toml not found. Copy settings.toml.example and edit it.")
        sys.exit(1)
    with CONFIG_FILE.open("rb") as fp:
        return tomllib.load(fp)


async def main() -> None:
    settings = load_settings()
    manager = EngineManager(settings)
    await manager.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Interrupted")
