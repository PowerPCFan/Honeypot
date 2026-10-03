import os


def env_bool(key: str, default: bool) -> bool:  # noqa: FBT001
    default_str = "true" if default else "false"
    true = {"1", "true", "yes", "on"}
    value = str(os.getenv(key, default_str)).lower()
    return bool(value in true)

DEBUG = env_bool("DEBUG", False)  # noqa: FBT003
DRY_RUN = env_bool("DRY_RUN", env_bool("DRYRUN", False))  # noqa: FBT003
