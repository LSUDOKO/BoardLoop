// BoardLoop template: blank ESP32 project.
// Prints a boot line, then a machine-readable heartbeat that tests can check.

void setup() {
  Serial.begin(115200);
  Serial.println("BOOT OK");
}

void loop() {
  static unsigned long tick = 0;
  Serial.print("TICK=");
  Serial.println(tick++);
  delay(500);
}
