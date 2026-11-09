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
