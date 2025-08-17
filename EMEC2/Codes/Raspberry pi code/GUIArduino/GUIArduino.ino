int PWM1 = 9;  // Motor 1 Rear Right
int IN1 = 4;
int IN2 = 5;
int PWM2 = 3;  // Motor 2 Rear Left
int IN3 = 6;
int IN4 = 7;
int PWM3 = 10; // Motor 3 Front Right
int IN5 = 8;
int IN6 = 2;
int PWM4 = 11; // Motor 4 Front Left
int IN7 = 12;
int IN8 = 13;

int motorSpeedLeft = 0;
int motorSpeedRight = 0;

void setup() {
  Serial.begin(9600);

  // Set all motor pins as output
  pinMode(PWM1, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(PWM2, OUTPUT); pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pinMode(PWM3, OUTPUT); pinMode(IN5, OUTPUT); pinMode(IN6, OUTPUT);
  pinMode(PWM4, OUTPUT); pinMode(IN7, OUTPUT); pinMode(IN8, OUTPUT);
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    controlMotors(command);
  }
}

void controlMotors(String command) {
  int motorSpeed = 250; // Adjust speed as needed

  if (command == "forward") {
    // Forward
    digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
    digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
    digitalWrite(IN5, LOW); digitalWrite(IN6, HIGH);
    digitalWrite(IN7, LOW); digitalWrite(IN8, HIGH);
    analogWrite(PWM1, motorSpeed);
    analogWrite(PWM2, motorSpeed);
    analogWrite(PWM3, motorSpeed);
    analogWrite(PWM4, motorSpeed);
  } else if (command == "backward") {
    // Backward
    digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
    digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
    digitalWrite(IN5, HIGH); digitalWrite(IN6, LOW);
    digitalWrite(IN7, HIGH); digitalWrite(IN8, LOW);
    analogWrite(PWM1, motorSpeed);
    analogWrite(PWM2, motorSpeed);
    analogWrite(PWM3, motorSpeed);
    analogWrite(PWM4, motorSpeed);
  } else if (command == "left") {
    // Left
    digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
    digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
    digitalWrite(IN5, HIGH); digitalWrite(IN6, LOW);
    digitalWrite(IN7, LOW); digitalWrite(IN8, HIGH);
    analogWrite(PWM1, motorSpeed);
    analogWrite(PWM2, motorSpeed);
    analogWrite(PWM3, motorSpeed);
    analogWrite(PWM4, motorSpeed);
  } else if (command == "right") {
    // Right
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, HIGH);
    digitalWrite(IN3, HIGH);
    digitalWrite(IN4, LOW);
    digitalWrite(IN5, LOW);
    digitalWrite(IN6, HIGH);
    digitalWrite(IN7, HIGH);
    digitalWrite(IN8, LOW);
    analogWrite(PWM1, motorSpeed);
    analogWrite(PWM2, motorSpeed);
    analogWrite(PWM3, motorSpeed);
    analogWrite(PWM4, motorSpeed);
  } else if (command == "stop") {
    // Stop
    analogWrite(PWM1, 0);
    analogWrite(PWM2, 0);
    analogWrite(PWM3, 0);
    analogWrite(PWM4, 0);
  }
}
