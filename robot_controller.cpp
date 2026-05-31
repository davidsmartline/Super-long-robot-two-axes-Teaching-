// 一轴超长臂示教控制 Arduino 程序
// 编码器 A/B：Pin 2, Pin 3
// 电机驱动：按你之前的 TB6600 / H桥 / 驱动板接线可改

#define ENC_A 2
#define ENC_B 3

#define PIN_AIN1 45
#define PIN_AIN2 47
#define PIN_AIN3 49
#define PIN_AIN4 51
#define PIN_PWM  9

volatile long encoderCount = 0;

bool movingToTarget = false;
long targetCount = 0;
int moveSpeed = 160;
long tolerance = 5;

void encoderISR() {
  int a = digitalRead(ENC_A);
  int b = digitalRead(ENC_B);

  if (a == b) encoderCount++;
  else encoderCount--;
}

void motorStop() {
  analogWrite(PIN_PWM, 0);
  digitalWrite(PIN_AIN1, LOW);
  digitalWrite(PIN_AIN2, LOW);
  digitalWrite(PIN_AIN3, LOW);
  digitalWrite(PIN_AIN4, LOW);
}

void motorForward(int spd) {
  spd = constrain(spd, 0, 255);
  digitalWrite(PIN_AIN3, LOW);
  digitalWrite(PIN_AIN4, LOW);
  digitalWrite(PIN_AIN1, HIGH);
  digitalWrite(PIN_AIN2, HIGH);
  analogWrite(PIN_PWM, spd);
}

void motorReverse(int spd) {
  spd = constrain(spd, 0, 255);
  digitalWrite(PIN_AIN1, LOW);
  digitalWrite(PIN_AIN2, LOW);
  digitalWrite(PIN_AIN3, HIGH);
  digitalWrite(PIN_AIN4, HIGH);
  analogWrite(PIN_PWM, spd);
}

void moveToPosition(long target, int spd) {
  targetCount = target;
  moveSpeed = constrain(spd, 0, 255);
  movingToTarget = true;
}

void updateAutoMove() {
  if (!movingToTarget) return;

  long current = encoderCount;
  long error = targetCount - current;

  if (abs(error) <= tolerance) {
    motorStop();
    movingToTarget = false;
    Serial.println("DONE");
    return;
  }

  if (error > 0) {
    motorForward(moveSpeed);
  } else {
    motorReverse(moveSpeed);
  }
}

void processCommand(String cmd) {
  cmd.trim();

  if (cmd.startsWith("FWD")) {
    int spd = cmd.substring(4).toInt();
    movingToTarget = false;
    motorForward(spd);
    Serial.println("OK FWD");
  }

  else if (cmd.startsWith("REV")) {
    int spd = cmd.substring(4).toInt();
    movingToTarget = false;
    motorReverse(spd);
    Serial.println("OK REV");
  }

  else if (cmd == "STOP") {
    movingToTarget = false;
    motorStop();
    Serial.println("OK STOP");
  }

  else if (cmd == "POS") {
    Serial.print("POS ");
    Serial.println(encoderCount);
  }

  else if (cmd == "ZERO") {
    encoderCount = 0;
    Serial.println("OK ZERO");
  }

  else if (cmd.startsWith("MOVE")) {
    // 格式：MOVE 12345 160
    int firstSpace = cmd.indexOf(' ');
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);

    if (firstSpace > 0 && secondSpace > firstSpace) {
      long pos = cmd.substring(firstSpace + 1, secondSpace).toInt();
      int spd = cmd.substring(secondSpace + 1).toInt();
      moveToPosition(pos, spd);
      Serial.println("OK MOVE");
    } else {
      Serial.println("ERR MOVE FORMAT");
    }
  }

  else {
    Serial.println("ERR UNKNOWN");
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(ENC_A, INPUT_PULLUP);
  pinMode(ENC_B, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(ENC_A), encoderISR, CHANGE);

  pinMode(PIN_AIN1, OUTPUT);
  pinMode(PIN_AIN2, OUTPUT);
  pinMode(PIN_AIN3, OUTPUT);
  pinMode(PIN_AIN4, OUTPUT);
  pinMode(PIN_PWM, OUTPUT);

  motorStop();

  Serial.println("LONG ARM TEACH READY");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    processCommand(cmd);
  }

  updateAutoMove();
}
