# FarmSight — Complete Project Documentation (Part 2)
# IoT Integration, API Architecture, Deployment & Interview Q&A

---

## CHAPTER 8: IoT INTEGRATION — THE HARDWARE SIDE

### What is IoT?

IoT (Internet of Things) means connecting physical devices (sensors, machines) to the internet so they can send data automatically. In our project, we connect farm sensors to our web app.

### Our Hardware Setup

**ESP32 Microcontroller** — The "brain" of our IoT system. It's a small, cheap ($5) chip with built-in WiFi. It reads all sensors and sends data over the internet.

**Three Sensors Connected to ESP32:**

#### 1. DHT11 — Temperature & Humidity Sensor
- **What it measures:** Air temperature (°C) and relative humidity (%)
- **How it works:** Contains a thermistor (resistance changes with temperature) and a capacitive humidity sensor (capacitance changes with moisture)
- **Connection:** Digital pin 13 on ESP32
- **Accuracy:** ±2°C temperature, ±5% humidity
- **In our code:**
```cpp
float h = dht.readHumidity();
float tC = dht.readTemperature();  // Celsius
tempF = (tC * 9.0 / 5.0) + 32.0;  // Convert to Fahrenheit
```
**Why Fahrenheit?** The original code stored in °F. Our Flask backend converts it back to °C:
```python
temp_c = round((temp_f - 32) * 5.0 / 9.0, 2)
```

#### 2. BMP280 — Barometric Pressure Sensor
- **What it measures:** Atmospheric pressure in hPa (hectopascals)
- **How it works:** Contains a piezo-resistive element that changes resistance when pressure is applied
- **Connection:** I2C protocol (uses SDA and SCL wires), address 0x76
- **Why pressure matters for crops:** Low pressure = incoming rain. High pressure = clear skies. Pressure patterns correlate with weather systems that affect crop growth
```cpp
pressure = bmp.readPressure() / 100.0;  // Convert Pa to hPa
```

#### 3. NPK Sensor (via RS485)
- **What it measures:** Nitrogen (N), Phosphorus (P), Potassium (K) in mg/kg
- **How it works:** Uses electrical conductivity probes inserted into soil. Different nutrients change soil conductivity differently
- **Connection:** RS485 serial protocol (industrial standard for long-distance communication)
- **Why RS485?** Regular serial (UART) works only up to 15 meters. RS485 works up to 1200 meters — essential for large farms where the sensor might be far from the controller
- **Communication:** Modbus protocol — the ESP32 sends a query command, the sensor responds with data
```cpp
// Modbus query: Read 3 registers starting at address 0x0000
byte query[] = {0x01, 0x03, 0x00, 0x00, 0x00, 0x03, 0x05, 0xCB};
// 0x01 = device address
// 0x03 = function code (read holding registers)
// 0x00, 0x00 = starting register
// 0x00, 0x03 = number of registers (3: N, P, K)
// 0x05, 0xCB = CRC checksum
```
- **Why NPK?** Nitrogen, Phosphorus, and Potassium are the THREE most important soil nutrients for plant growth. They're literally on every fertilizer bag (e.g., 10-10-10 means 10% N, 10% P, 10% K)

### The LCD Display
Shows real-time readings on a 16×2 character display, alternating between:
- NPK values (5 seconds)
- Temperature/Humidity/Pressure (4 seconds)

This gives the farmer immediate visual feedback without needing a phone.

---

## CHAPTER 9: THE DATA FLOW — ESP32 TO FORM

### Complete Data Journey

```
STEP 1: ESP32 reads sensors every 2 seconds
        DHT11 → tempF=85.5, humidity=60.2
        BMP280 → pressure=1013.25
        NPK → N=45, P=30, K=25

STEP 2: Every 30 seconds, ESP32 sends HTTP POST
        URL: https://farmsight-kj6r.onrender.com/api/iot-upload
        Headers: {Content-Type: application/json, X-API-Key: farmsight-iot-2026}
        Body: {"tempF":85.5, "humidity":60.2, "pressure":1013.25, "N":45, "P":30, "K":25}

STEP 3: Flask receives the POST request
        @app.route('/api/iot-upload', methods=['POST'])
        → Validates API key
        → Adds timestamp
        → Inserts into MongoDB: sensor_collection.insert_one(data)

STEP 4: MongoDB Atlas stores it as a document
        {
          "_id": ObjectId("auto-generated"),
          "tempF": 85.5,
          "humidity": 60.2,
          "pressure": 1013.25,
          "N": 45, "P": 30, "K": 25,
          "timestamp": "2026-04-29T01:00:00Z"
        }

STEP 5: User clicks "Fill from IoT Sensor" button
        JavaScript calls: fetch('/api/iot-data')

STEP 6: Flask queries MongoDB for the LATEST document
        latest = sensor_collection.find_one(sort=[("_id", -1)])
        → Converts tempF to Celsius
        → Returns JSON to browser

STEP 7: JavaScript fills the form
        document.getElementById('temperature').value = data.temperature
        document.getElementById('humidity').value = data.humidity
        ... and so on for pressure, N, P, K
```

### Why This Architecture?

**Q: Why not send data directly from ESP32 to MongoDB?**
A: MongoDB's Data API was deprecated in 2024. Also, routing through our Flask app lets us add authentication, validation, and logging.

**Q: Why not send directly from ESP32 to the browser?**
A: The browser and ESP32 are on different networks. They can't talk directly. MongoDB acts as the "shared mailbox" — ESP32 drops off data, browser picks it up.

**Q: Why MongoDB and not SQLite?**
A: SQLite is a file on ONE server's disk. The ESP32 (on a farm WiFi) can't write to a file on Render's server. MongoDB Atlas is a cloud database accessible from anywhere with an internet connection.

### API Security

We use a simple API key authentication:
```python
api_key = request.headers.get('X-API-Key', '')
expected_key = os.getenv('IOT_API_KEY', 'farmsight-iot-2026')
if api_key != expected_key:
    return jsonify({"error": "Unauthorized"}), 401
```
The ESP32 includes this key in every request. Without it, random people can't inject fake sensor data.

---

## CHAPTER 10: THE FULL-STACK WEB APPLICATION

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | HTML, CSS, Bootstrap, JavaScript | User interface |
| Backend | Flask (Python) | API routes, business logic |
| ML Model | CatBoost | Crop yield predictions |
| Auth DB | SQLite (SQLAlchemy) | User accounts |
| IoT DB | MongoDB Atlas | Sensor data storage |
| IoT Hardware | ESP32 + DHT11 + BMP280 + NPK | Live farm data |
| Deployment | Render.com | Cloud hosting |
| VCS | GitHub | Code management |

### Authentication System

- **Registration:** Username, email, password (hashed with PBKDF2-SHA256)
- **Login:** With OTP verification via email (Flask-Mail + Gmail SMTP)
- **Password Reset:** Timed token sent via email (expires in 10 minutes)
- **Session Management:** Flask-Login handles "remember me" and route protection

### Key Routes

| Route | Method | What It Does |
|-------|--------|-------------|
| `/register` | GET/POST | User registration |
| `/login` | GET/POST | User login with OTP |
| `/` | GET | Home page (requires login) |
| `/test_application` | GET | Shows prediction form |
| `/predict1` | POST | Runs CatBoost prediction |
| `/get_districts` | POST | Returns districts for a state |
| `/get_avg_weather` | POST | Returns avg weather for district |
| `/api/iot-upload` | POST | Receives ESP32 sensor data |
| `/api/iot-data` | GET | Returns latest IoT reading |
| `/disease-predict` | POST | Upload dataset for analysis |
| `/preprocessing_data` | GET | Shows data cleaning results |
| `/eda_data` | GET | Shows EDA visualizations |
| `/models_data` | GET | Shows model comparison |

---

## CHAPTER 11: DEPLOYMENT ON RENDER

### What is Render?
Render is a cloud platform (like Heroku) that runs your code on their servers 24/7. Free tier gives 512MB RAM, auto-deploys from GitHub.

### Deployment Files

**Procfile** — Tells Render how to start the app:
```
web: gunicorn main:app
```
- `gunicorn` = production-grade Python web server (handles multiple requests simultaneously)
- `main:app` = import `app` object from `main.py`

**requirements.txt** — Lists all Python packages to install:
```
flask, catboost, pandas, numpy, pymongo, gunicorn, etc. (21 packages)
```

**Runtime.txt** — Specifies Python version:
```
python-3.12.2
```

### Environment Variables on Render
```
SECRET_KEY=supersecretkey123
MAIL_USERNAME=sunharshini@gmail.com
MAIL_PASSWORD=atvw dxxe kfuz zcyb
MONGO_URI=mongodb+srv://myAtlasDBUser:...@myatlasclusteredu.tsuer.mongodb.net/SoilDB
```

### Why Gunicorn Instead of Flask's Built-in Server?
Flask's development server handles ONE request at a time. If 10 users visit simultaneously, 9 have to wait. Gunicorn spawns multiple worker processes to handle requests in parallel.

---

## CHAPTER 12: POTENTIAL INTERVIEW QUESTIONS & ANSWERS

### Data & ML Questions

**Q1: Why did you choose CatBoost over XGBoost or Random Forest?**
A: Three reasons: (1) CatBoost handles categorical features like State, District, Crop Name natively without needing one-hot encoding. Our dataset has 5 categorical columns with hundreds of unique values — one-hot encoding would create thousands of columns and make the model slow. (2) CatBoost's Ordered Boosting prevents target leakage during training, giving better generalization. (3) In our comparison tests, CatBoost achieved the highest test R² score.

**Q2: What is gradient boosting in simple terms?**
A: Imagine a student taking a test. After getting results, they study ONLY the questions they got wrong. Next test, they do better on those but might miss others. So they study the NEW mistakes. After repeating this 1000 times, they've covered every possible question type. Gradient boosting works the same way — each new tree fixes the mistakes of all previous trees.

**Q3: Why did you use log transformation on the target variable?**
A: Production values are heavily skewed — most farms produce 1-100 tons, but some produce 1,000,000 tons. Without log transform, the model focuses on getting the big values right and ignores small farms. Log compression brings all values to a similar range, so the model learns patterns for ALL farm sizes equally.

**Q4: How do you handle missing values and why?**
A: For numerical columns, we use Random Value Imputation — randomly sampling existing values to fill gaps. This preserves the statistical distribution (mean and variance) of the data. For categorical columns, we use Mode Imputation — filling with the most frequent category. We chose random imputation over mean imputation because mean imputation artificially reduces variance and can bias the model.

**Q5: What is R² score and what does it tell you?**
A: R² measures how much of the variation in crop production our model can explain. An R² of 0.85 means our model explains 85% of why some farms produce more than others. The remaining 15% is due to factors not in our data (like pest attacks, farmer skill, irrigation quality).

**Q6: What is overfitting and how does CatBoost prevent it?**
A: Overfitting is when a model memorizes training data instead of learning patterns. Like a student who memorizes answers but can't solve new problems. CatBoost prevents it through: (1) Ordered Boosting — uses only past data points for each prediction, (2) L2 regularization — penalizes complex models, (3) Early stopping — stops adding trees when test accuracy stops improving.

### IoT Questions

**Q7: How does the ESP32 send data to the web app?**
A: The ESP32 connects to WiFi, then makes an HTTPS POST request to our Flask API endpoint (`/api/iot-upload`) every 30 seconds. It sends a JSON payload containing temperature, humidity, pressure, N, P, K values. The Flask app receives this, adds a timestamp, and stores it in MongoDB Atlas.

**Q8: Why did you use RS485 for the NPK sensor instead of regular serial?**
A: RS485 is an industrial communication standard designed for noisy, long-distance environments like farms. Regular serial (UART) works up to 15 meters; RS485 works up to 1200 meters. Farms are large, and the NPK sensor may be placed far from the controller. RS485 also uses differential signaling, which is resistant to electromagnetic interference from farm equipment.

**Q9: Why send data through Flask instead of directly to MongoDB?**
A: MongoDB's Data API was deprecated in September 2024. More importantly, routing through our Flask app gives us: (1) Authentication — we verify the API key before accepting data, (2) Data validation — we can check if values are reasonable, (3) Centralized logging — all data flows through one point, (4) Flexibility — we can add preprocessing or alerts without changing the ESP32 code.

**Q10: What happens if the ESP32 loses WiFi?**
A: The code checks `WiFi.status() == WL_CONNECTED` before each upload. If WiFi is lost, it calls `WiFi.reconnect()` and skips that upload cycle. Data is NOT lost — the sensors continue reading and the LCD continues displaying. The next successful upload will send the current readings. However, historical readings during the offline period are not stored (a future improvement could add local SD card buffering).

### Architecture Questions

**Q11: Why two databases (SQLite + MongoDB)?**
A: They serve different purposes. SQLite stores user accounts (username, email, hashed password) — this is structured, relational data that's accessed only by the Flask app. MongoDB stores IoT sensor data — this is time-series data that's written by the ESP32 and read by the browser. Using the right database for each job is better than forcing one database to do everything.

**Q12: How is the app secured?**
A: Multiple layers: (1) Passwords are hashed with PBKDF2-SHA256 before storage, (2) OTP verification via email during login, (3) CSRF protection via Flask-WTF on all forms, (4) API key authentication for IoT endpoint, (5) `@login_required` decorator blocks unauthenticated access to all routes, (6) Password reset tokens expire after 10 minutes.

**Q13: What are the limitations of your project?**
A: (1) Free Render tier has 512MB RAM — CatBoost model is 33MB, leaving limited room for concurrent users. (2) SQLite on Render doesn't persist across deploys — user data is lost on redeployment. A production system should use PostgreSQL. (3) The model assumes historical weather patterns continue — climate change could reduce accuracy over time. (4) NPK sensor readings in mg/kg may need calibration for different soil conditions. (5) Free tier sleeps after 15 minutes of inactivity.

**Q14: If you had more time, what would you improve?**
A: (1) Add a dashboard showing historical sensor trends with charts, (2) Implement push notifications when sensor values indicate crop stress, (3) Add GPS coordinates for multi-farm support, (4) Use PostgreSQL for persistent user data, (5) Add model retraining pipeline when new production data comes in, (6) Implement offline data buffering on ESP32 with SD card.

**Q15: Explain the complete flow from a farmer opening the app to getting a prediction.**
A: The farmer opens farmsight-kj6r.onrender.com → logs in with username/email/OTP → sees the home page → clicks "Start Prediction" → fills the prediction form (selects state, district, crop, season, area) → clicks "Fill from IoT Sensor" which auto-fills temperature, humidity, pressure, N, P, K from live sensor data → adjusts any values if needed → clicks "Predict Crop Yield" → JavaScript sends form data to /predict1 → Flask encodes categorical values using saved LabelEncoders → builds a 15-feature vector → CatBoost model predicts in log-space → Flask converts back with expm1() → returns "Estimated Production: X tons" → displayed on screen.
