"""register(), the TOOLS table and plugin.yaml must agree (catalog rule 6)."""
import inspect

import yaml

import boardloop
from boardloop import tools
from conftest import ROOT


class FakeCtx:
    def __init__(self, config=None):
        self.tools, self.hooks, self.commands, self.skills = {}, {}, {}, {}
        self.config = config or {}

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def register_tool(self, name, toolset, schema, handler, check_fn=None, **kw):
        assert toolset == "boardloop" and schema["name"] == name
        self.tools[name] = (handler, check_fn)

    def register_hook(self, name, cb, **kw):
        self.hooks[name] = cb

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands[name] = handler

    def register_skill(self, name, path, description=""):
        assert path.is_file()
        self.skills[name] = path


def manifest():
    return yaml.safe_load((ROOT / "plugin.yaml").read_text())


def test_declared_equals_registered():
    ctx = FakeCtx()
    boardloop.register(ctx)
    m = manifest()
    assert list(ctx.tools) == m["provides_tools"] == [n for n, _, _ in tools.TOOLS]
    assert list(ctx.hooks) == m["provides_hooks"] == ["pre_tool_call"]
    assert list(ctx.commands) == ["mcu"] and list(ctx.skills) == ["boardloop"]


def test_tool_prefix_and_handler_signature():
    for name, schema, handler in tools.TOOLS:
        assert name.startswith("mcu_")
        params = inspect.signature(handler).parameters
        assert any(p.kind == p.VAR_KEYWORD for p in params.values()), name
        assert schema["description"] and schema["parameters"]["type"] == "object"


def test_hooks_accept_kwargs():
    from boardloop import approvals, commands
    for fn in (approvals.on_pre_tool_call, commands.handle):
        assert any(p.kind == p.VAR_KEYWORD for p in inspect.signature(fn).parameters.values())


def test_version_matches():
    assert manifest()["version"] == boardloop.__version__
    assert manifest()["requires_hermes"].startswith(">=")


def test_config_schema_matches_settings():
    keys = set(manifest()["config_schema"]) - {"wokwi_token"}
    from boardloop import config
    fields = {f for f in config.Settings.__dataclass_fields__} - {"data_dir", "workspace_dir", "extra"}
    assert keys == fields | {"workspace_dir"}


def test_dependencies_have_upper_bounds():
    for dep in manifest()["python_dependencies"]:
        assert ">=" in dep and "<" in dep.split(">=", 1)[1], dep


def test_settings_reach_handlers():
    ctx = FakeCtx({"compile_budget": 7})
    boardloop.register(ctx)
    assert tools.RUNTIME.settings().compile_budget == 7
    tools.RUNTIME.configure(lambda k, d=None: d)
