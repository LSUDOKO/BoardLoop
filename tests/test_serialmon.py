import pytest

from boardloop import serialmon


class FakePort:
    def __init__(self, chunks):
        self.chunks, self.written = list(chunks), b""

    def __call__(self, port, baud, **kw):
        self.port, self.baud = port, baud
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        return self.chunks.pop(0) if self.chunks else b""

    def write(self, data):
        self.written += data
        return len(data)

    def flush(self):
        pass


def test_read_lines_and_stop_early():
    port = FakePort([b"BOOT OK\r\nT=24.0 ", b"H=40.0 LED=OFF\r\n", b"never read\n"])
    lines = serialmon.read("/dev/ttyUSB0", 115200, seconds=5, until_text="LED=", opener=port)
    assert lines == ["BOOT OK", "T=24.0 H=40.0 LED=OFF"]


def test_read_caps_lines():
    port = FakePort([b"".join(f"l{i}\n".encode() for i in range(200))])
    assert len(serialmon.read("COM3", 9600, seconds=0.5, opener=port)) == serialmon.MAX_LINES


def test_write_appends_newline():
    port = FakePort([])
    assert serialmon.write("COM3", 115200, "SET 30", opener=port) == 7 and port.written == b"SET 30\n"


@pytest.mark.parametrize("port,ok", [("/dev/ttyUSB0", True), ("/dev/cu.usbserial-0001", True), ("COM12", True),
                                     ("/dev/sda", False), ("/dev/ttyUSB0; rm -rf /", False), ("COM9999", False)])
def test_port_pattern(port, ok):
    assert bool(serialmon.PORT_RE.match(port)) is ok


def test_expectations():
    assert serialmon.check_expectations(["BOOT OK", "LED=ON"], ["BOOT", "LED=ON"]) == (True, "all expected lines seen")
    assert serialmon.check_expectations(["LED=ON"], ["BOOT"])[0] is False
