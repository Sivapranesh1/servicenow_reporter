"""Load YAML configuration and environment variables."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is invalid."""


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load YAML configuration; environment variables override sensitive keys."""
    load_dotenv()
    path = Path(config_path or os.getenv("CONFIG_FILE", "./config/config.yaml"))

    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Merge SMTP secrets from env
    cfg.setdefault("email", {}).update(
        {
            "smtp_host": os.getenv("SMTP_HOST"),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "smtp_user": os.getenv("SMTP_USER"),
            "smtp_password": os.getenv("SMTP_PASSWORD"),
            "smtp_use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            "from_address": os.getenv("SMTP_FROM_ADDRESS"),
            "from_name": os.getenv("SMTP_FROM_NAME", "ServiceNow Reporter"),
        }
    )
    return cfg
