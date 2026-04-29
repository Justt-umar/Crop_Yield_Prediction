#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <Adafruit_BMP280.h>
#include <WiFi.h>
#include <HTTPClient.h>

// --- CONFIGURATION ---
const char* ssid = "Umar";
const char* password = "Umarkhan";

// FarmSight Flask App (Deployed on Render)
const char* serverUrl = "https://farmsight-kj6r.onrender.com/api/iot-upload";
const char* apiKey = "farmsight-iot-2026";

// --- HARDWARE PINOUT ---
#define DHTPIN 13
#define DHTTYPE DHT11
#define DE_PIN 4
#define RE_PIN 5
#define RS485_BAUD 4800
#define RS485_SERIAL Serial2 // Pins 16 (RX), 17 (TX)

// --- INSTANCES ---
LiquidCrystal_I2C lcd(0x27, 16, 2);
DHT dht(DHTPIN, DHTTYPE);
Adafruit_BMP280 bmp;

// --- STATE & TIMING ---
enum DisplayState { SHOW_NPK, SHOW_ENV };
DisplayState currentState = SHOW_NPK;

unsigned long lastStateChange = 0;
unsigned long lastSensorRead = 0;
unsigned long lastDisplayUpdate = 0;
unsigned long lastServerUpload = 0;

const unsigned long NPK_DISPLAY_TIME = 5000;
const unsigned long ENV_DISPLAY_TIME = 4000;
const unsigned long DISPLAY_UPDATE_INTERVAL = 500;
const unsigned long SENSOR_READ_INTERVAL = 2000;
const unsigned long UPLOAD_INTERVAL = 30000; // 30 seconds

// --- DATA STRUCTURES ---
struct NPKData {
  float nitrogen;
  float phosphorus;
  float potassium;
};

NPKData npkData = {0, 0, 0};
float humidity = 0;
float tempF = 0;
float pressure = 0;

void setup() {
  Serial.begin(115200);

  // Initialize LCD
  lcd.init();
  lcd.backlight();
  lcd.print("Initializing...");

  // Initialize Sensors
  dht.begin();
  if (!bmp.begin(0x76)) {
    Serial.println("BMP280 not found!");
    lcd.clear();
    lcd.print("BMP Error!");
  }

  // RS485 Setup
  pinMode(DE_PIN, OUTPUT);
  pinMode(RE_PIN, OUTPUT);
  setRS485Receive();
  RS485_SERIAL.begin(RS485_BAUD, SERIAL_8N1, 16, 17);

  // WiFi Setup
  WiFi.begin(ssid, password);
  Serial.print("WiFi connecting");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    lcd.clear();
    lcd.print("WiFi Connected!");
  } else {
    Serial.println("\nWiFi Failed!");
    lcd.clear();
    lcd.print("WiFi Failed!");
  }

  delay(2000);
  lcd.clear();
}

void loop() {
  unsigned long currentTime = millis();

  // 1. READ SENSORS
  if (currentTime - lastSensorRead >= SENSOR_READ_INTERVAL) {
    readDHT();
    readBMP();
    lastSensorRead = currentTime;
  }

  // 2. MANAGE DISPLAY CYCLES
  if (currentState == SHOW_NPK) {
    if (currentTime - lastStateChange >= NPK_DISPLAY_TIME) {
      currentState = SHOW_ENV;
      lastStateChange = currentTime;
      lcd.clear();
    }
  } else {
    if (currentTime - lastStateChange >= ENV_DISPLAY_TIME) {
      currentState = SHOW_NPK;
      lastStateChange = currentTime;
      lcd.clear();
    }
  }

  // 3. UPDATE LCD & READ NPK
  if (currentTime - lastDisplayUpdate >= DISPLAY_UPDATE_INTERVAL) {
    if (currentState == SHOW_NPK) {
      readNPK();
      displayNPK();
    } else {
      displayENV();
    }
    lastDisplayUpdate = currentTime;
  }

  // 4. UPLOAD TO SERVER (EVERY 30 SECONDS)
  if (currentTime - lastServerUpload >= UPLOAD_INTERVAL) {
    if (WiFi.status() == WL_CONNECTED) {
      uploadToServer();
    } else {
      Serial.println("WiFi Offline - Reconnecting...");
      WiFi.reconnect();
    }
    lastServerUpload = currentTime;
  }
}

// -------- SENSOR FUNCTIONS --------

void setRS485Transmit() {
  digitalWrite(DE_PIN, HIGH);
  digitalWrite(RE_PIN, HIGH);
}

void setRS485Receive() {
  digitalWrite(DE_PIN, LOW);
  digitalWrite(RE_PIN, LOW);
}

void readDHT() {
  float h = dht.readHumidity();
  float tC = dht.readTemperature();
  if (!isnan(h) && !isnan(tC)) {
    humidity = h;
    tempF = (tC * 9.0 / 5.0) + 32.0;
  }
}

void readBMP() {
  pressure = bmp.readPressure() / 100.0; 
}

void readNPK() {
  byte query[] = {0x01, 0x03, 0x00, 0x00, 0x00, 0x03, 0x05, 0xCB};
  setRS485Transmit();
  RS485_SERIAL.write(query, sizeof(query));
  RS485_SERIAL.flush();
  setRS485Receive();

  delay(100); 

  if (RS485_SERIAL.available() >= 11) {
    byte response[11];
    RS485_SERIAL.readBytes(response, 11);
    if (response[0] == 0x01 && response[1] == 0x03) {
      npkData.nitrogen = (response[3] << 8 | response[4]) / 1.0;
      npkData.phosphorus = (response[5] << 8 | response[6]) / 1.0;
      npkData.potassium = (response[7] << 8 | response[8]) / 1.0;
    }
  }
}

// -------- SERVER UPLOAD (Flask App on Render) --------

void uploadToServer() {
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);
  http.setTimeout(15000); // 15 second timeout (Render free tier may wake up slowly)

  // Construct JSON payload
  String payload = "{";
  payload += "\"tempF\":" + String(tempF, 2) + ",";
  payload += "\"humidity\":" + String(humidity, 2) + ",";
  payload += "\"pressure\":" + String(pressure, 2) + ",";
  payload += "\"N\":" + String(npkData.nitrogen, 1) + ",";
  payload += "\"P\":" + String(npkData.phosphorus, 1) + ",";
  payload += "\"K\":" + String(npkData.potassium, 1);
  payload += "}";

  Serial.println("[Upload] Sending: " + payload);
  int httpCode = http.POST(payload);
  
  if (httpCode > 0) {
    String response = http.getString();
    Serial.printf("[Upload] Status: %d | Response: %s\n", httpCode, response.c_str());
  } else {
    Serial.printf("[Upload] Failed: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

// -------- DISPLAY FUNCTIONS --------

void displayNPK() {
  lcd.setCursor(0, 0);
  lcd.print("N:"); lcd.print(npkData.nitrogen, 0);
  lcd.print(" P:"); lcd.print(npkData.phosphorus, 0);
  lcd.print("   ");
  lcd.setCursor(0, 1);
  lcd.print("K:"); lcd.print(npkData.potassium, 0);
  lcd.print(" mg/kg    ");
}

void displayENV() {
  lcd.setCursor(0, 0);
  lcd.print("T:"); lcd.print(tempF, 1);
  lcd.print("F H:"); lcd.print(humidity, 0);
  lcd.print("% ");
  lcd.setCursor(0, 1);
  lcd.print("P:"); lcd.print(pressure, 0);
  lcd.print(" hPa     ");
}
