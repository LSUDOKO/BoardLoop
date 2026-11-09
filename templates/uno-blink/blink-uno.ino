// BoardLoop sample: Arduino Uno blink with a button.
// LED on pin 13 blinks every 500 ms; holding the button (pin 2) keeps it on.

const int LED_PIN = 13;
const int BUTTON_PIN = 2;

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.println("BOOT OK");
}

void loop() {
  bool pressed = digitalRead(BUTTON_PIN) == LOW;
  if (pressed) {
    digitalWrite(LED_PIN, HIGH);
    Serial.println("BUTTON=DOWN LED=ON");
    delay(100);
    return;
  }
  digitalWrite(LED_PIN, HIGH);
  Serial.println("LED=ON");
  delay(500);
  digitalWrite(LED_PIN, LOW);
  Serial.println("LED=OFF");
  delay(500);
}
