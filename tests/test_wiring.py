import json

from boardloop import wiring
from conftest import EXAMPLES


def diagram(name):
    return json.loads((EXAMPLES / name / "diagram.json").read_text())


def test_trace_led_through_resistor():
    assert wiring.trace_to_board(diagram("thermostat"), "led1:A") == ["esp:26"]
    assert wiring.trace_to_board(diagram("blink-uno"), "led1:A") == ["uno:13"]


def test_trace_direct_and_unconnected():
    d = diagram("thermostat")
    assert wiring.trace_to_board(d, "dht1:SDA") == ["esp:4"]
    assert wiring.trace_to_board(d, "dht1:NC") == []


def test_gpio_number():
    assert wiring.gpio_number("esp:26") == 26
    assert wiring.gpio_number("esp:GND.1") is None
    assert wiring.gpio_number("uno:13") == 13


def rules(d):
    return sorted({w["rule"] for w in wiring.check(d) if w["level"] != "info"})


def test_examples_are_clean():
    assert rules(diagram("thermostat")) == []
    assert rules(diagram("blink-uno")) == []
    assert [w["rule"] for w in wiring.check(diagram("thermostat"))] == ["oled_vcc_5v"]


def test_detects_input_only_pin():
    d = diagram("thermostat")
    d["connections"] = [c if c[0] != "esp:26" else ["esp:35", "r1:1", "", []] for c in d["connections"]]
    assert "input_only_pin" in rules(d)


def test_detects_led_without_resistor_and_no_ground():
    d = diagram("thermostat")
    d["connections"] = [c for c in d["connections"] if "r1" not in c[0] + c[1] and c[0] != "led1:C"]
    d["connections"].append(["esp:26", "led1:A", "", []])
    assert {"led_without_resistor", "no_ground"} <= set(rules(d))


def test_detects_unknown_part_and_strapping_button():
    d = diagram("thermostat")
    d["parts"].append({"type": "wokwi-pushbutton", "id": "btn1", "top": 0, "left": 0, "attrs": {}})
    d["connections"] += [["btn1:1.l", "esp:0", "", []], ["ghost:1", "esp:GND.1", "", []]]
    assert {"strapping_pin_button", "unknown_part"} <= set(rules(d))
