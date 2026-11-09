import yaml

from boardloop import scenario

HOT = {"name": "hot room turns the LED on", "sensors": {"dht1": {"temperature": "35"}},
       "controls": [], "run_ms": 3000, "expect_serial": ["LED=ON"],
       "expect_pins": [{"part": "led1", "pin": "A", "value": 1}], "screenshot": "oled1"}


def test_full_scenario_shape():
    doc = yaml.safe_load(scenario.build(HOT, "BOOT OK"))
    assert doc["name"] == HOT["name"] and doc["version"] == 1 and doc["author"] == "BoardLoop"
    assert doc["steps"] == [
        {"wait-serial": "BOOT OK"},
        {"wait-serial": "LED=ON"},
        {"delay": "3000ms"},
        {"expect-pin": {"part-id": "led1", "name": "A", "value": 1}},
        {"take-screenshot": {"part-id": "oled1", "save-to": "hot-room-turns-the-led-on-oled1.png"}},
    ]


def test_controls_come_after_boot_and_use_name_key():
    t = dict(HOT, controls=[{"part": "btn1", "control": "pressed", "value": 1}], screenshot="")
    steps = yaml.safe_load(scenario.build(t, "BOOT OK"))["steps"]
    assert steps[1] == {"set-control": {"part-id": "btn1", "name": "pressed", "value": 1}}
    assert not any("take-screenshot" in s for s in steps)


def test_no_boot_text_and_multiple_serial_in_order():
    t = dict(HOT, expect_serial=["LED=ON", "LED=OFF"], expect_pins=[], screenshot="")
    steps = yaml.safe_load(scenario.build(t))["steps"]
    assert steps == [{"wait-serial": "LED=ON"}, {"wait-serial": "LED=OFF"}, {"delay": "3000ms"}]


def test_weird_names_round_trip_safely():
    t = dict(HOT, name='it\'s "hot": 35°C # not a comment', expect_serial=["A: b", "- x"])
    doc = yaml.safe_load(scenario.build(t, "BOOT: OK"))
    assert doc["name"] == t["name"]
    assert doc["steps"][0] == {"wait-serial": "BOOT: OK"}
    assert doc["steps"][2] == {"wait-serial": "- x"}


def test_timeout_budget():
    assert scenario.timeout_ms(HOT) == 3000 + 3000 + 1000 + 2000
    assert scenario.timeout_ms(dict(HOT, run_ms=15000, expect_serial=["a"] * 10)) == 20000


def test_slug():
    assert scenario.slug("Exactly 30 C is not too hot!") == "exactly-30-c-is-not-too-hot"
    assert scenario.slug("***") == "test"


def test_waits():
    assert scenario.waits(HOT, "BOOT OK") == ["BOOT OK", "LED=ON"]
