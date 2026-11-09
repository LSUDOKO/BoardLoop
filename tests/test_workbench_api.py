"""dashboard/plugin_api.py: the Workbench pane's data, built from a real tool run."""
import importlib.util

from conftest import ROOT
from test_tools import call, env, new  # noqa: F401
from boardloop import tools


def api():
    spec = importlib.util.spec_from_file_location("bl_plugin_api", ROOT / "dashboard" / "plugin_api.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_overview_and_detail_after_a_verify(env):
    new()
    assert call("mcu_verify", project="demo1")["status"] == "verified"
    settings = tools.RUNTIME.settings()
    m = api()
    ov = m.overview(settings.data_dir, settings.workspace_dir, 50)
    assert ov["minutes"]["used"] > 0
    assert ov["projects"] == [{"name": "demo1", "last_verify": ov["projects"][0]["last_verify"]}]
    assert ov["projects"][0]["last_verify"]["status"] == "verified"
    d = m.project_detail(settings.data_dir, "demo1")
    assert d["tests"]["passed"] == 3 and len(d["tests"]["results"]) == 3
    assert d["tests"]["results"][0]["image"].startswith("data:image/png;base64,")
    assert {"verify", "compile", "test"} <= {h["stage"] for h in d["history"]}


def test_detail_rejects_bad_names_and_foreign_files(env, tmp_path):
    m = api()
    settings = tools.RUNTIME.settings()
    assert m.project_detail(settings.data_dir, "../etc") == {"error": "bad project name"}
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"\x89PNG")
    assert m._shot(settings.data_dir, str(outside)) is None


def test_empty_data_dir(tmp_path):
    m = api()
    assert m.overview(tmp_path, tmp_path / "ws") == {"minutes": {"used": 0.0, "limit": 50}, "projects": []}
    assert m.project_detail(tmp_path, "x")["tests"] is None
