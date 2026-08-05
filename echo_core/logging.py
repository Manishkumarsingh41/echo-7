from __future__ import annotations

import logging


def configure_logging(level_name: str) -> None:
    """Configure lightweight application logging."""
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
