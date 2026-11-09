"""BoardLoop projects: the ``boardloop.yaml`` format, path safety, templates and circuit tables.

A project is a folder ``<workspace>/<name>/`` holding ``<name>.ino``, ``diagram.json``,
``wokwi.toml`` and ``boardloop.yaml``. The folder and sketch share the name (an arduino-cli rule).
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import BOARD_ALIASES

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
PART_ID_RE = re.compile(r"^[A-Za-z_][\w-]{0,40}$")
MAX_TESTS = 20
MAX_LIST = 10
MAX_STR = 200
RUN_MS_RANGE = (100, 15_000)
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATES = ("esp32-blank", "esp32-thermostat", "uno-blink")
PROJECT_FILES = ("diagram.json", "wokwi.toml", "boardloop.yaml")


class ProjectError(Exception):
    """A user-facing problem with a project. ``code`` is one of the tool error codes."""

    def __init__(self, code: str, message: str, hint: str = ""):
        super().__init__(message)
        self.code, self.message, self.hint = code, message, hint


# --- path safety ---------------------------------------------------------------------------------

def safe_child(root: Path, name: str) -> Path:
    """Resolve ``root/name`` and require it to stay inside ``root`` (no ``..``, absolute paths or
    symlinks pointing out)."""
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ProjectError("bad_args", "Empty or invalid path.")
    if Path(name).is_absolute() or ".." in Path(name).parts:
        raise ProjectError("path_outside_workspace", f"'{name}' points outside the workspace.",
                           "Use a plain project name such as 'thermostat'.")
    root_r = root.resolve()
    target = (root / name).resolve()
    if target != root_r and root_r not in target.parents:
        raise ProjectError("path_outside_workspace", f"'{name}' resolves outside the workspace.",
                           "Symlinks that leave the workspace are not allowed.")
    return target


def validate_name(name: Any) -> str:
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ProjectError("bad_args", f"Invalid project name {name!r}.",
                           "Use lowercase letters, digits and '-', starting with a letter or digit "
                           "(max 41 chars), e.g. 'plant-alarm'.")
    return name


def project_dir(workspace: Path, name: Any) -> Path:
    """Folder of an existing project, safely resolved."""
    validate_name(name)
    path = safe_child(workspace, name)
    if not (path / "boardloop.yaml").is_file():
        raise ProjectError("project_not_found", f"No project '{name}' in the workspace.",
                           "List projects with /mcu projects, or create one with mcu_project_new.")
    return path


def list_projects(workspace: Path) -> list[str]:
    if not workspace.is_dir():
        return []
    return sorted(p.name for p in workspace.iterdir()
                  if p.is_dir() and not p.is_symlink() and (p / "boardloop.yaml").is_file())


# --- project file --------------------------------------------------------------------------------

@dataclass
class Project:
    name: str
    path: Path
    board: str
    fqbn: str
    sketch: str
    libraries: list[str] = field(default_factory=list)
    boot_text: str = ""
    fail_text: str = ""
    tests: list[dict] = field(default_factory=list)
    diagram: dict = field(default_factory=dict)

    @property
    def is_esp32(self) -> bool:
        return self.fqbn.startswith("esp32:")

    @property
    def firmware_rel(self) -> str:
        ext = "bin" if self.is_esp32 else "hex"
        return f"build/{self.sketch}.{ext}"

    @property
    def elf_rel(self) -> str:
        return f"build/{self.sketch}.elf"

    def part_ids(self) -> set[str]:
        return {p.get("id") for p in self.diagram.get("parts", []) if isinstance(p, dict)}


def _str(value: Any, what: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ProjectError("bad_args", f"{what} must be text.")
    s = str(value)
    if len(s) > MAX_STR:
        raise ProjectError("bad_args", f"{what} is longer than {MAX_STR} characters.")
    return s


def _list(value: Any, what: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProjectError("bad_args", f"{what} must be a list.")
    if len(value) > MAX_LIST:
        raise ProjectError("bad_args", f"{what} has more than {MAX_LIST} items.")
    return value


def validate_test(test: Any, part_ids: set[str], index: int = 0) -> dict:
    """Check one test dict and return a normalised copy. Unknown part ids are rejected so the
    agent can't test parts that aren't in the circuit."""
    if not isinstance(test, dict):
        raise ProjectError("bad_args", f"Test #{index + 1} must be a mapping.")
    name = _str(test.get("name"), f"Test #{index + 1} name").strip()
    if not name:
        raise ProjectError("bad_args", f"Test #{index + 1} needs a name.")
    where = f"Test '{name}'"

    def known(part: Any) -> str:
        part = _str(part, f"{where} part id")
        if part not in part_ids:
            raise ProjectError("bad_args", f"{where} uses part '{part}', which is not in diagram.json.",
                               f"Known parts: {', '.join(sorted(p for p in part_ids if p))}. "
                               "Read them with mcu_project_info.")
        return part

    sensors_in = test.get("sensors") or {}
    if not isinstance(sensors_in, dict) or len(sensors_in) > MAX_LIST:
        raise ProjectError("bad_args", f"{where}: sensors must map part ids to attributes.")
    sensors: dict[str, dict[str, str]] = {}
    for part, attrs in sensors_in.items():
        part = known(part)
        if not isinstance(attrs, dict) or len(attrs) > MAX_LIST:
            raise ProjectError("bad_args", f"{where}: sensors.{part} must be a mapping of attributes.")
        sensors[part] = {_str(k, "attribute name"): _str(v, f"{part}.{k}") for k, v in attrs.items()}

    controls = []
    for c in _list(test.get("controls"), f"{where} controls"):
        if not isinstance(c, dict):
            raise ProjectError("bad_args", f"{where}: each control needs part, control, value.")
        control = _str(c.get("control", c.get("name")), f"{where} control name")
        if not control:
            raise ProjectError("bad_args", f"{where}: a control is missing its name (e.g. 'pressed').")
        controls.append({"part": known(c.get("part")), "control": control,
                         "value": _number(c.get("value"), f"{where} control value")})

    run_ms = test.get("run_ms", 2000)
    if not isinstance(run_ms, int) or isinstance(run_ms, bool) or not (
            RUN_MS_RANGE[0] <= run_ms <= RUN_MS_RANGE[1]):
        raise ProjectError("bad_args", f"{where}: run_ms must be a whole number from "
                                       f"{RUN_MS_RANGE[0]} to {RUN_MS_RANGE[1]}.")

    expect_serial = [_str(s, f"{where} expect_serial") for s in _list(test.get("expect_serial"),
                                                                       f"{where} expect_serial")]
    if any(not s for s in expect_serial):
        raise ProjectError("bad_args", f"{where}: expect_serial entries can't be empty.")
    pins = []
    for p in _list(test.get("expect_pins"), f"{where} expect_pins"):
        if not isinstance(p, dict):
            raise ProjectError("bad_args", f"{where}: each expect_pins item needs part, pin, value.")
        value = p.get("value")
        if value not in (0, 1) or isinstance(value, bool):
            raise ProjectError("bad_args", f"{where}: pin values are 0 or 1.")
        pin = _str(p.get("pin", p.get("name")), f"{where} pin")
        if not pin:
            raise ProjectError("bad_args", f"{where}: expect_pins item is missing 'pin'.")
        pins.append({"part": known(p.get("part")), "pin": pin, "value": value})

    screenshot = test.get("screenshot")
    screenshot = known(screenshot) if screenshot else ""
    return {"name": name, "sensors": sensors, "controls": controls, "run_ms": run_ms,
            "expect_serial": expect_serial, "expect_pins": pins, "screenshot": screenshot}


def _number(value: Any, what: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectError("bad_args", f"{what} must be a number.")
    return value


def validate_tests(tests: Any, part_ids: set[str]) -> list[dict]:
    if tests is None:
        return []
    if not isinstance(tests, list):
        raise ProjectError("bad_args", "tests must be a list.")
    if len(tests) > MAX_TESTS:
        raise ProjectError("bad_args", f"At most {MAX_TESTS} tests per project.")
    out = [validate_test(t, part_ids, i) for i, t in enumerate(tests)]
    names = [t["name"] for t in out]
    if len(set(names)) != len(names):
        raise ProjectError("bad_args", "Test names must be unique.")
    return out


def load_diagram(path: Path) -> dict:
    try:
        data = json.loads((path / "diagram.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProjectError("bad_args", "diagram.json is missing.") from None
    except json.JSONDecodeError as exc:
        raise ProjectError("bad_args", f"diagram.json is not valid JSON: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("parts"), list):
        raise ProjectError("bad_args", "diagram.json needs a 'parts' list.")
    return data


def load(workspace: Path, name: Any) -> Project:
    """Load and validate a project from the workspace."""
    path = project_dir(workspace, name)
    try:
        raw = yaml.safe_load((path / "boardloop.yaml").read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProjectError("bad_args", f"boardloop.yaml is not valid YAML: {exc}") from None
    if not isinstance(raw, dict):
        raise ProjectError("bad_args", "boardloop.yaml must be a mapping.")
    if raw.get("name", name) != name:
        raise ProjectError("bad_args", f"boardloop.yaml name '{raw.get('name')}' must match the "
                                       f"folder '{name}'.")
    board = str(raw.get("board") or "esp32").lower()
    fqbn = str(raw.get("fqbn") or BOARD_ALIASES.get(board, ""))
    if not re.match(r"^[\w.-]+:[\w.-]+:[\w.-]+(:[\w=,.-]+)?$", fqbn):
        raise ProjectError("bad_args", f"Unknown board '{board}' and no valid fqbn.",
                           f"Use one of {', '.join(BOARD_ALIASES)} or set fqbn (e.g. esp32:esp32:esp32).")
    sketch = str(raw.get("sketch") or f"{name}.ino")
    if sketch != f"{name}.ino":
        raise ProjectError("bad_args", f"sketch must be '{name}.ino' (arduino-cli needs the folder "
                                       "and sketch to share a name).")
    libraries = [_str(lib, "library name") for lib in _list(raw.get("libraries"), "libraries")]
    diagram = load_diagram(path)
    part_ids = {p.get("id") for p in diagram["parts"] if isinstance(p, dict)}
    return Project(
        name=name, path=path, board=board, fqbn=fqbn, sketch=sketch, libraries=libraries,
        boot_text=_str(raw.get("boot_text"), "boot_text"), fail_text=_str(raw.get("fail_text"), "fail_text"),
        tests=validate_tests(raw.get("tests"), part_ids), diagram=diagram,
    )


def add_library(project: Project, library: str) -> None:
    """Append a library to ``boardloop.yaml`` (keeps the rest of the file as parsed YAML)."""
    path = project.path / "boardloop.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    libs = list(raw.get("libraries") or [])
    if library not in libs:
        libs.append(library)
        raw["libraries"] = libs
        path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")


# --- circuit tables ------------------------------------------------------------------------------

def parts_table(diagram: dict) -> list[dict]:
    return [{"id": p.get("id"), "type": p.get("type"), "attrs": p.get("attrs") or {}}
            for p in diagram.get("parts", []) if isinstance(p, dict)]


def connections(diagram: dict) -> list[tuple[str, str]]:
    """Wire endpoints, without the serial-monitor links."""
    out = []
    for c in diagram.get("connections", []):
        if not isinstance(c, list) or len(c) < 2:
            continue
        a, b = str(c[0]), str(c[1])
        if a.startswith("$") or b.startswith("$"):
            continue
        out.append((a, b))
    return out


def wiring_table(diagram: dict) -> list[str]:
    return [f"{a} → {b}" for a, b in connections(diagram)]


# --- templates -----------------------------------------------------------------------------------

def wokwi_toml(sketch: str, esp32: bool) -> str:
    ext = "bin" if esp32 else "hex"
    return ("[wokwi]\nversion = 1\n"
            f"# Produced by: arduino-cli compile --output-dir build .\n"
            f"firmware = 'build/{sketch}.{ext}'\nelf = 'build/{sketch}.elf'\n")


def create_from_template(workspace: Path, name: Any, template: str) -> Project:
    """Copy a template into ``<workspace>/<name>`` and rename sketch, yaml and wokwi.toml."""
    validate_name(name)
    if template not in TEMPLATES:
        raise ProjectError("bad_args", f"Unknown template '{template}'.", f"Use one of {', '.join(TEMPLATES)}.")
    workspace.mkdir(parents=True, exist_ok=True)
    dest = safe_child(workspace, name)
    if dest.exists():
        raise ProjectError("bad_args", f"Project '{name}' already exists.", "Pick another name.")
    src = TEMPLATES_DIR / template
    raw = yaml.safe_load((src / "boardloop.yaml").read_text(encoding="utf-8"))
    old_sketch = src / raw["sketch"]
    dest.mkdir()
    try:
        shutil.copyfile(src / "diagram.json", dest / "diagram.json")
        shutil.copyfile(old_sketch, dest / f"{name}.ino")
        raw["name"], raw["sketch"] = name, f"{name}.ino"
        (dest / "boardloop.yaml").write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
                                             encoding="utf-8")
        fqbn = raw.get("fqbn") or BOARD_ALIASES.get(raw.get("board", "esp32"), "")
        (dest / "wokwi.toml").write_text(wokwi_toml(f"{name}.ino", fqbn.startswith("esp32:")),
                                         encoding="utf-8")
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    return load(workspace, name)


def import_folder(workspace: Path, src: Path, name: str) -> Project:
    """Copy an existing project folder (e.g. one of ``examples/``) into the workspace."""
    validate_name(name)
    dest = safe_child(workspace, name)
    if dest.exists():
        raise ProjectError("bad_args", f"Project '{name}' already exists.")
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("build", "screenshots", "*.bin", "*.elf", "*.hex"))
    return load(workspace, name)
