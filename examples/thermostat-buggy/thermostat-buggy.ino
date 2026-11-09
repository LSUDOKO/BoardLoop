// BoardLoop DEMO: deliberately broken thermostat.
// Bug 1 (compile): missing semicolon.  Bug 2 (logic): LED condition is reversed.
// Ask Hermes: "Make the thermostat-buggy project pass its tests."
// Reads a DHT22, shows temperature and humidity on an SSD1306 OLED,
// and turns the red LED on when the temperature is above THRESHOLD_C.
//
// Wiring (see diagram.json):
//   DHT22 data -> GPIO 4      OLED SDA -> GPIO 21, SCL -> GPIO 22
//   LED anode  -> 220R -> GPIO 26, LED cathode -> GND
//
// Serial lines are machine-readable so BoardLoop tests can check them:
//   BOOT OK
//   T=35.0 H=50.0 LED=ON

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHTesp.h>

const int DHT_PIN = 4;
const int LED_PIN = 26;
const float THRESHOLD_C = 30.0

Adafruit_SSD1306 display(128, 64, &Wire, -1);
DHTesp dht;

void showReading(float t, float h, bool ledOn) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("BoardLoop thermostat");
  display.setTextSize(2);
  display.setCursor(0, 18);
  display.print(t, 1);
  display.println(" C");
  display.setTextSize(1);
  display.setCursor(0, 42);
  display.print("Humidity ");
  display.print(h, 0);
  display.println(" %");
  display.setCursor(0, 54);
  display.println(ledOn ? "ALERT: too hot" : "OK");
  display.display();
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  dht.setup(DHT_PIN, DHTesp::DHT22);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("ERROR: OLED not found");
    for (;;) {
      delay(1000);
    }
  }
  display.clearDisplay();
  display.display();
  Serial.println("BOOT OK");
}

void loop() {
  TempAndHumidity data = dht.getTempAndHumidity();
  if (dht.getStatus() != DHTesp::ERROR_NONE) {
    Serial.print("ERROR: DHT ");
    Serial.println(dht.getStatusString());
    delay(1000);
    return;
  }

  bool ledOn = data.temperature < THRESHOLD_C;
  digitalWrite(LED_PIN, ledOn ? HIGH : LOW);
  showReading(data.temperature, data.humidity, ledOn);

  Serial.print("T=");
  Serial.print(data.temperature, 1);
  Serial.print(" H=");
  Serial.print(data.humidity, 1);
  Serial.print(" LED=");
  Serial.println(ledOn ? "ON" : "OFF");

  delay(1000);
}
