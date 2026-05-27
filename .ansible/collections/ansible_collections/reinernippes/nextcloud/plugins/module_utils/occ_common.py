from __future__ import annotations

import json
import os
import shlex
from typing import Any


# Environment variable names for common parameters
ENV_PHP_RUNTIME = "NEXTCLOUD_PHP_RUNTIME"
ENV_OCC_PATH = "NEXTCLOUD_OCC_PATH"
ENV_WEB_USER = "NEXTCLOUD_WEB_USER"


MISSING_VALUE_HINTS = (
    "not found",
    "does not exist",
    "not set",
    "could not be found",
    "no such",
)


def normalize_indices(value: Any) -> list[str]:
    """Turn indices parameter into a flat list of string path components.

    Accepts: None, a single scalar, or a list of scalars.
    Returns: list of str (possibly empty).
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def apply_env_defaults(params: dict[str, Any], module: Any = None) -> None:
    """Apply environment variable fallbacks for occ_path, php_bin, and web_user.

    Checks os.environ first, then module.run_command_environ_update (which is
    where Ansible injects play-level ``environment:`` directives).
    Only overrides a parameter when the user did not explicitly set it
    (i.e. it still holds its default or is None/empty).
    """
    def _env(key: str) -> str | None:
        val = os.environ.get(key)
        if not val and module is not None:
            val = getattr(module, "run_command_environ_update", {}).get(key)
        return val

    if params.get("php_bin") in (None, "php") and _env(ENV_PHP_RUNTIME):
        params["php_bin"] = _env(ENV_PHP_RUNTIME)
    if not params.get("occ_path") and _env(ENV_OCC_PATH):
        params["occ_path"] = _env(ENV_OCC_PATH)
    if not params.get("web_user") and _env(ENV_WEB_USER):
        params["web_user"] = _env(ENV_WEB_USER)


def default_chdir(occ_path: str, chdir: str | None = None) -> str:
    if chdir:
        return chdir
    return os.path.dirname(os.path.abspath(occ_path))


def build_occ_command(php_bin: str, occ_path: str, argv: list[str] | None = None, command: str | None = None, web_user: str | None = None) -> list[str]:
    if bool(argv) == bool(command):
        raise ValueError("exactly one of 'argv' or 'command' must be provided")

    cmd = []
    if web_user:
        cmd.extend(["sudo", "-u", str(web_user)])
    cmd.extend([str(php_bin), str(occ_path)])
    if command is not None:
        cmd.extend(shlex.split(command))
    else:
        cmd.extend([str(item) for item in argv or []])
    return cmd


def run_occ(module, php_bin: str, occ_path: str, chdir: str | None = None, argv: list[str] | None = None, command: str | None = None, check_rc: bool = False, environ_update: dict[str, str] | None = None, web_user: str | None = None) -> dict[str, Any]:
    cwd = default_chdir(occ_path, chdir)
    cmd = build_occ_command(php_bin=php_bin, occ_path=occ_path, argv=argv, command=command, web_user=web_user)
    rc, stdout, stderr = module.run_command(cmd, cwd=cwd, environ_update=environ_update or {})
    result = {
        "rc": rc,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_lines": stdout.splitlines(),
        "cmd": cmd,
        "chdir": cwd,
    }
    if check_rc and rc != 0:
        module.fail_json(msg="occ command failed", **result)
    return result


def parse_json_output(stdout: str) -> Any:
    text = (stdout or "").strip()
    if not text:
        return None
    return json.loads(text)


def extract_app_sets(app_list_payload: Any) -> tuple[set[str], set[str]]:
    enabled_section = {}
    disabled_section = {}
    if isinstance(app_list_payload, dict):
        enabled_section = app_list_payload.get("enabled", {})
        disabled_section = app_list_payload.get("disabled", {})

    def _names(section: Any) -> set[str]:
        if isinstance(section, dict):
            return {str(key) for key in section.keys()}
        if isinstance(section, list):
            return {str(item) for item in section}
        return set()

    return _names(enabled_section), _names(disabled_section)


def config_value_from_output(stdout: str) -> Any:
    lines = [line.rstrip("\n") for line in (stdout or "").splitlines()]
    if not lines:
        return ""
    if len(lines) == 1:
        return lines[0]
    return lines


def format_cli_value(value: Any, value_type: str) -> str:
    if value_type == "json":
        if isinstance(value, str):
            return value
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    if value_type == "boolean":
        return "true" if normalize_scalar(value, value_type) else "false"
    if value_type == "null":
        return "null"
    return str(value)


def normalize_scalar(value: Any, value_type: str | None = None) -> Any:
    if value_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if value_type == "integer":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "null":
        return None
    return value


def values_equal(current_stdout: str, desired: Any, value_type: str) -> bool:
    current = config_value_from_output(current_stdout)

    if value_type == "json":
        if isinstance(desired, str):
            try:
                desired = json.loads(desired)
            except Exception:
                pass
        try:
            current_obj = json.loads((current_stdout or "").strip())
        except Exception:
            current_obj = current
        return current_obj == desired

    if isinstance(desired, list):
        if isinstance(current, list):
            return [str(item) for item in current] == [str(item) for item in desired]
        return False

    if isinstance(desired, bool) or value_type == "boolean":
        return normalize_scalar(current, "boolean") == normalize_scalar(desired, "boolean")

    if desired is None and value_type == "null":
        return normalize_scalar(current, "null") is None

    if value_type in ("integer", "float"):
        try:
            return normalize_scalar(current, value_type) == normalize_scalar(desired, value_type)
        except Exception:
            return False

    return str(current).strip() == str(desired).strip()


def looks_like_missing_value(result: dict[str, Any]) -> bool:
    combined = " ".join([
        str(result.get("stdout", "")),
        str(result.get("stderr", "")),
    ]).strip().lower()
    return result.get("rc", 0) != 0 and (not combined or any(token in combined for token in MISSING_VALUE_HINTS))
