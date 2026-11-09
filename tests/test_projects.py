import os
import shutil

import pytest
import yaml

from boardloop import projects
from boardloop.projects import ProjectError
from conftest import EXAMPLES


@pytest.fixture
def ws(tmp_path):
    w = tmp_path / "ws"
    w.mkdir()
    for name in ("thermostat", "thermostat-buggy", "blink-uno"):
        shutil.copytree(EXAMPLES / name, w / name)
    return w


@pytest.mark.parametrize("name", ["thermostat", "a", "plant-alarm-2", "9volt"])
def test_good_names(name):
    assert projects.validate_name(name) == name


@pytest.mark.parametrize("name", ["", "-x", "Thermo", "a b", "a_b", "x" * 42, "../etc", None, 5])
def test_bad_names(name):
    with pytest.raises(ProjectError):
        projects.validate_name(name)


@pytest.mark.parametrize("bad", ["../x", "/etc", "a/../../b"])
def test_path_escape_blocked(tmp_path, bad):
    with pytest.raises(ProjectError) as e:
        projects.safe_child(tmp_path, bad)
    assert e.value.code == "path_outside_workspace"


@pytest.mark.skipif(os.name == "nt", reason="symlinks need admin on Windows")
def test_symlink_escape_blocked(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "evil").symlink_to(tmp_path)
    with pytest.raises(ProjectError) as e:
        projects.safe_child(ws, "evil/outside")
    assert e.value.code == "path_outside_workspace"


def test_load_thermostat(ws):
    p = projects.load(ws, "thermostat")
    assert p.fqbn == "esp32:esp32:esp32" and p.is_esp32
    assert p.firmware_rel == "build/thermostat.ino.bin"
    assert [t["name"] for t in p.tests] == [
        "hot room turns the LED on", "cool room keeps the LED off", "exactly 30 C is not too hot"]
    hot = p.tests[0]
    assert hot["sensors"] == {"dht1": {"temperature": "35", "humidity": "50"}}  # values become strings
    assert hot["expect_pins"] == [{"part": "led1", "pin": "A", "value": 1}]


def test_load_uno_uses_hex(ws):
    p = projects.load(ws, "blink-uno")
    assert not p.is_esp32 and p.firmware_rel == "build/blink-uno.ino.hex"
    assert p.tests[1]["controls"] == [{"part": "btn1", "control": "pressed", "value": 1}]


def test_missing_project(ws):
    with pytest.raises(ProjectError) as e:
        projects.load(ws, "nope")
    assert e.value.code == "project_not_found"


def test_list_projects(ws):
    assert projects.list_projects(ws) == ["blink-uno", "thermostat", "thermostat-buggy"]


def _edit_yaml(ws, name, fn):
    path = ws / name / "boardloop.yaml"
    raw = yaml.safe_load(path.read_text())
    fn(raw)
    path.write_text(yaml.safe_dump(raw))


def test_unknown_part_in_test_rejected(ws):
    _edit_yaml(ws, "thermostat", lambda r: r["tests"][0]["expect_pins"][0].update(part="led9"))
    with pytest.raises(ProjectError) as e:
        projects.load(ws, "thermostat")
    assert "led9" in e.value.message and "led1" in e.value.hint


@pytest.mark.parametrize("mutate", [
    lambda r: r["tests"][0].update(run_ms=50),
    lambda r: r["tests"][0].update(run_ms="3000"),
    lambda r: r["tests"][0].update(expect_serial=["x"] * 11),
    lambda r: r["tests"][0]["expect_pins"][0].update(value=2),
    lambda r: r["tests"][0].update(name="x" * 201),
    lambda r: r.update(tests=[r["tests"][0]] * 2),          # duplicate names
    lambda r: r.update(tests=[{"name": f"t{i}"} for i in range(21)]),
    lambda r: r.update(sketch="other.ino"),
    lambda r: r.update(name="different"),
    lambda r: r.update(board="toaster", fqbn=None),
])
def test_invalid_yaml_rejected(ws, mutate):
    _edit_yaml(ws, "thermostat", mutate)
    with pytest.raises(ProjectError):
        projects.load(ws, "thermostat")


def test_parts_and_wiring_tables(ws):
    p = projects.load(ws, "thermostat")
    parts = projects.parts_table(p.diagram)
    assert len(parts) == 5
    wiring = projects.wiring_table(p.diagram)
    assert len(wiring) == 10                       # serial-monitor links excluded
    assert "dht1:SDA → esp:4" in wiring and "esp:26 → r1:1" in wiring
    assert not any("$serialMonitor" in w for w in wiring)


def test_add_library(ws):
    p = projects.load(ws, "blink-uno")
    projects.add_library(p, "Servo")
    projects.add_library(p, "Servo")
    assert projects.load(ws, "blink-uno").libraries == ["Servo"]


def test_import_folder_skips_build_outputs(tmp_path):
    src = tmp_path / "src" / "thermostat"
    shutil.copytree(EXAMPLES / "thermostat", src)
    (src / "build").mkdir()
    (src / "build" / "thermostat.ino.bin").write_text("x")
    ws = tmp_path / "ws"
    p = projects.import_folder(ws, src, "thermostat")
    assert not (p.path / "build").exists()


@pytest.mark.parametrize("template,board", [
    ("esp32-thermostat", "esp32"), ("uno-blink", "uno"), ("esp32-blank", "esp32")])
def test_templates_create_consistent_projects(tmp_path, template, board):
    p = projects.create_from_template(tmp_path, "demo1", template)
    files = sorted(f.name for f in p.path.iterdir())
    assert files == ["boardloop.yaml", "demo1.ino", "diagram.json", "wokwi.toml"]
    assert p.name == "demo1" and p.sketch == "demo1.ino" and p.board == board
    toml = (p.path / "wokwi.toml").read_text()
    assert f"'{p.firmware_rel}'" in toml and "build/demo1.ino.elf" in toml
    assert p.tests, "every template ships at least one passing test"


def test_template_name_clash_and_unknown(tmp_path):
    projects.create_from_template(tmp_path, "demo1", "esp32-blank")
    with pytest.raises(ProjectError):
        projects.create_from_template(tmp_path, "demo1", "esp32-blank")
    with pytest.raises(ProjectError):
        projects.create_from_template(tmp_path, "demo2", "toaster")
    assert not (tmp_path / "demo2").exists()


def test_templates_match_examples():
    for tpl, ex in (("esp32-thermostat", "thermostat"), ("uno-blink", "blink-uno")):
        assert (projects.TEMPLATES_DIR / tpl / f"{ex}.ino").read_text() == (EXAMPLES / ex / f"{ex}.ino").read_text()


def test_demo_template_keeps_the_planted_bugs(tmp_path):
    p = projects.create_from_template(tmp_path, "thermostat-buggy", "demo-thermostat-buggy")
    src = (p.path / "thermostat-buggy.ino").read_text()
    assert "THRESHOLD_C = 30.0\n" in src and "< THRESHOLD_C" in src


def test_blank_template_retarget(tmp_path):
    p = projects.create_from_template(tmp_path, "s3", "esp32-blank", board="esp32s3")
    assert p.fqbn == "esp32:esp32:esp32s3"
    assert p.diagram["parts"][0]["type"] == "board-esp32-s3-devkitc-1"
    with pytest.raises(ProjectError):
        projects.create_from_template(tmp_path, "t2", "esp32-thermostat", board="uno")
