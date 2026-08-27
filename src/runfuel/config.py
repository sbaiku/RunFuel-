"""Environment-backed settings."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = "runfuel.db"
DEFAULT_WEIGHT_KG = 70.0


@dataclass(frozen=True)
class Settings:
    db_path: Path
    weight_kg: float


def load_settings() -> Settings:
    """Build settings from the environment, falling back to defaults."""
    return Settings(
        db_path=Path(os.environ.get("RUNFUEL_DB_PATH", DEFAULT_DB_PATH)),
        weight_kg=float(os.environ.get("RUNFUEL_WEIGHT_KG", DEFAULT_WEIGHT_KG)),
    )
