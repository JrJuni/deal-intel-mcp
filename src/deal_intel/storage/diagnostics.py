from __future__ import annotations


def local_sample_mode_hint() -> dict[str, str]:
    """Return the standard hint for entering MongoDB-free sample mode."""

    return {
        "purpose": (
            "Use the bundled read-only sample dataset when MongoDB Atlas is not "
            "configured yet."
        ),
        "temporary_env": "DEAL_INTEL_STORAGE_BACKEND=local_sample",
        "powershell": "$env:DEAL_INTEL_STORAGE_BACKEND='local_sample'",
        "user_config_path": "~/.deal-intel/config.yaml",
        "user_config": "storage:\n  backend: local_sample",
        "diagnostic_command": "python -m deal_intel.cli storage-status",
    }


def missing_mongodb_uri_message() -> str:
    return (
        "MONGODB_URI is not set for storage.backend=mongo. "
        "Set MONGODB_URI in .env for Atlas-backed storage, or switch to "
        "local sample mode with DEAL_INTEL_STORAGE_BACKEND=local_sample."
    )


def missing_mongodb_uri_ping(*, database: str) -> dict:
    return {
        "status": "missing_uri",
        "storage_backend": "mongo",
        "database": database,
        "message": missing_mongodb_uri_message(),
        "fix": "Set MONGODB_URI in .env (see .env.example).",
        "sample_mode_hint": local_sample_mode_hint(),
    }
