# FarmSight — Complete Project Documentation (Part 1)
# Data Pipeline, CatBoost Model & Machine Learning

---

## CHAPTER 1: PROJECT OVERVIEW

### What is FarmSight?

FarmSight is an end-to-end **Crop Yield Prediction System** that combines **Machine Learning** with **IoT (Internet of Things)** to help farmers predict how much crop they will produce. 

Think of it like a weather forecast, but instead of predicting rain, we predict "How many tons of rice will this 10-hectare farm in Tamil Nadu produce this Kharif season?"

### The Problem We're Solving

Indian farmers face a critical question every season: "How much will my farm produce?" The answer depends on dozens of factors — weather, soil nutrients, location, crop type, season, area of land, and more. Traditionally, farmers rely on experience and guesswork. FarmSight replaces guesswork with data-driven predictions.

### What Makes Our Project Unique?

1. **Real IoT Integration** — We don't just use historical data. Our ESP32 microcontroller reads LIVE sensor data (temperature, humidity, pressure, NPK nutrients) from the actual farm
2. **CatBoost Model** — We tested multiple ML models and selected CatBoost because it handles categorical data (like State names, Crop names) natively
3. **Full-Stack Deployment** — The app is live on the internet at https://farmsight-kj6r.onrender.com
4. **246,000+ records** — Our model is trained on a massive all-India agricultural dataset

---

## CHAPTER 2: DATA GATHERING

### The Dataset

Our dataset (`output.csv`) contains **246,091 records** covering agricultural data across all Indian states and districts.

**16 columns (features):**

| Column | Type | Example | Source |
|--------|------|---------|--------|
| State | Categorical | "Tamil Nadu" | Government agricultural records |
| District | Categorical | "CHENNAI" | Government agricultural records |
| Crop Year | Numerical | 2000-2020 | Government agricultural records |
| Season | Categorical | "Kharif", "Rabi", "Whole Year" | Government agricultural records |
| Crop Name | Categorical | "Rice", "Wheat", "Arecanut" | Government agricultural records |
| Area (hectares) | Numerical | 1254.0 | Government agricultural records |
| Temperature (°C) | Numerical | 292.64 (in Kelvin originally) | Weather API / Historical data |
| Wind Speed (m/s) | Numerical | 2.38 | Weather API |
| Precipitation (mm) | Numerical | 1016.87 | Weather API |
| Humidity (%) | Numerical | 43 | Weather API |
| Soil Type | Categorical | "clay", "sandy", "peaty" | Soil survey data |
| Nitrogen (N) | Numerical | 598.55 | Soil nutrient analysis |
| Phosphorus (P) | Numerical | 0.0 | Soil nutrient analysis |
| Potassium (K) | Numerical | 0.0 | Soil nutrient analysis |
| **Production (tons)** | **Numerical (TARGET)** | **2000** | **Government records** |
| Pressure (hPa) | Numerical | 1004 | Weather API |

**The TARGET variable is Production (tons)** — this is what we are trying to predict.

### Where Did the Data Come From?

The dataset merges multiple sources:
1. **data.gov.in** — Indian government's open data portal for crop production statistics
2. **OpenWeatherMap API** — Historical weather data (temperature, wind, humidity, pressure, precipitation) mapped to each district
3. **Soil Survey of India** — Soil type classification for each district
4. **Research literature** — NPK (Nitrogen, Phosphorus, Potassium) values for different soil types and regions

### Data Gathering Process

```
Step 1: Download raw crop production data from data.gov.in
        (State, District, Crop Year, Season, Crop, Area, Production)
                            ↓
Step 2: For each (State, District, Year), fetch weather data
        from OpenWeatherMap API using the weather_api_key
                            ↓
Step 3: Map soil types to each district based on
        geographical surveys
                            ↓
Step 4: Add NPK nutrient data based on soil analysis
        reports for each region
                            ↓
Step 5: Merge everything into one CSV: output.csv
        (246,091 rows × 16 columns)
```

---

## CHAPTER 3: DATA CLEANING & PREPROCESSING

### Why Do We Need Data Cleaning?

Real-world data is messy. Some weather stations didn't report data, some districts had missing crop records, some soil surveys were incomplete. If we feed messy data to our ML model, we get messy predictions. "Garbage in, garbage out."

### Our Cleaning Process (in `import_analyse.py`)

#### Step 1: Drop Unnecessary Columns
```python
df.drop('Unnamed: 0', axis=1, inplace=True, errors='ignore')
```
CSV files sometimes add an extra index column when saved. We remove it.

#### Step 2: Rename Columns for Clarity
```python
df.columns = ['State', 'District', 'Crop Year', 'Season', 'Crop Name', 
              'Area (hectares)', 'Temperature (°C)', 'Wind Speed (m/s)', 
              'Precipitation (mm)', 'Humidity (%)', 'Soil Type', 'Nitrogen (N)',
              'Phosphorus (P)', 'Potassium (K)', 'Production (tons)', 'Pressure (hPa)']
```

#### Step 3: Handle Missing Values — The Critical Step

We separate columns into two types:
- **Numerical columns** (numbers): Temperature, Area, N, P, K, etc.
- **Categorical columns** (text): State, District, Season, Crop Name, Soil Type

**For numerical missing values — Random Value Imputation:**
```python
def random_value_imputation(feature):
    random_sample = df[feature].dropna().sample(df[feature].isna().sum())
    random_sample.index = df[df[feature].isnull()].index
    df.loc[df[feature].isnull(), feature] = random_sample
```

**What this does in plain English:** If temperature is missing for 100 rows, we randomly pick 100 existing temperature values from the dataset and fill them in. This preserves the statistical distribution (mean, variance) of the data better than just filling with the average.

**Why not just use the mean?** If we fill all missing temperatures with 25°C (the mean), we artificially reduce the spread of the data. Random sampling maintains the natural variation.

**For categorical missing values — Mode Imputation:**
```python
def impute_mode(feature):
    mode = df[feature].mode()[0]
    df[feature] = df[feature].fillna(mode)
```

**What this does:** Fill missing categories with the most common value. If "Kharif" is the most common season, missing season values become "Kharif". This makes sense because most Indian agriculture is Kharif-dominant.

#### Step 4: Convert Production to Numeric
```python
df["Production (tons)"] = pd.to_numeric(df["Production (tons)"], errors='coerce')
df.dropna(subset=["Production (tons)"], inplace=True)
```
Some production values might be stored as text ("N/A", "-"). We convert to numbers and drop rows where production can't be parsed.

---

## CHAPTER 4: EXPLORATORY DATA ANALYSIS (EDA)

EDA means "looking at the data visually before building models." Our app generates three types of plots:

### 1. Numerical Distribution (Histograms with KDE)
Shows the spread of each numerical feature. For example:
- Is temperature normally distributed?
- Are most farms small (under 100 hectares) or large?
- Is production skewed (many small values, few very large)?

**Key finding:** Production is heavily right-skewed — most farms produce small amounts, but a few produce massive quantities. This is why we use **log transformation** (`np.log1p`) on the target variable during training.

### 2. Categorical Count Plots
Shows how many records exist for each category. For example:
- Which states have the most data?
- Which seasons dominate?
- Which crops are most common?

### 3. Correlation Heatmap
Shows which features are related to each other. A correlation of +1 means "as X increases, Y increases." A correlation of -1 means "as X increases, Y decreases." 0 means no relationship.

**Key findings:**
- Area and Production have strong positive correlation (bigger farms → more production)
- NPK values have moderate correlation with production
- Temperature and humidity have weaker but meaningful correlations

---

## CHAPTER 5: MODEL SELECTION — WHY CatBoost?

### The Models We Compared (in `models_details.py`)

We trained and tested **3 different models** on the same data:

| Model | How It Works | Train R² | Test R² |
|-------|-------------|----------|---------|
| Linear Regression | Draws a straight line through data | Low | Low |
| Decision Tree | Makes yes/no decisions in a tree structure | Very High (overfits) | Medium |
| Random Forest | Averages many decision trees | High | Good |
| **CatBoost** | **Gradient-boosted trees with categorical support** | **High** | **Best** |

### What Do These Metrics Mean?

**R² Score (R-squared):** Measures how well the model explains the variation in data.
- R² = 1.0 → Perfect predictions
- R² = 0.8 → Model explains 80% of the variation  
- R² = 0.0 → Model is no better than guessing the average

**MSE (Mean Squared Error):** Average of squared differences between predicted and actual values. Lower = better.

**Why not Linear Regression?** — Crop yield doesn't follow a straight line. The relationship between temperature and production isn't linear — too cold is bad, too hot is bad, moderate is good. Linear models can't capture this.

**Why not Decision Tree?** — A single decision tree tends to "memorize" the training data (overfitting). It might get 99% on training data but only 60% on new data.

**Why not Random Forest?** — Random Forest is good, but it can't handle categorical features (like "Tamil Nadu" or "Rice") directly. We'd need to convert them to numbers first, which loses information.

**Why CatBoost? — The Winner:**
CatBoost handles categorical features NATIVELY (no encoding needed), resists overfitting, and gave us the best test accuracy.

---

## CHAPTER 6: CatBoost — DEEP DIVE

### What is CatBoost?

CatBoost stands for **Cat**egorical **Boost**ing. It was developed by **Yandex** (the Russian search engine company) in 2017. It is a **gradient boosting** algorithm built on **decision trees**.

### What is Gradient Boosting? (Explained Simply)

Imagine you're trying to guess someone's weight:

**Step 1:** Your first guess is the average weight: 70 kg. The actual weight is 85 kg. Error = 15 kg.

**Step 2:** You build a small model that tries to predict the ERROR (15 kg). This model learns: "If the person is tall, add 10 kg." Now your prediction is 70 + 10 = 80 kg. Error = 5 kg.

**Step 3:** You build ANOTHER small model that tries to predict the REMAINING error (5 kg). This model learns: "If the person exercises, subtract 3 kg." Now: 80 - 3 = 77 kg. Error = 8 kg.

Wait, that's worse! So we don't add the full correction — we add only a small fraction (the **learning rate**). With learning rate = 0.1: 80 + (0.1 × -3) = 79.7 kg.

**Step 4, 5, 6... 1000:** Keep building small models, each one correcting the errors of all previous models combined.

**The final prediction = Sum of all small model predictions.**

This is gradient boosting: many weak learners (small trees) combined into one strong learner.

### What Makes CatBoost Special?

#### 1. Native Categorical Feature Handling

Other models (XGBoost, Random Forest) require you to convert "Tamil Nadu" to a number like 15. This is called **Label Encoding**. But this creates a fake ordering — the model might think State 15 > State 5, which is meaningless.

CatBoost uses **Ordered Target Statistics** instead:
- For each categorical value (like "Tamil Nadu"), it calculates the average target (production) for that category
- But it does this carefully to avoid data leakage (looking at future data)
- It processes rows one by one, using only PREVIOUSLY seen rows to calculate the statistic

#### 2. Ordered Boosting (Prevents Overfitting)

Traditional gradient boosting has a subtle problem: when calculating the error for row #500, it uses a model that was already trained on row #500. This is like grading your own exam — biased!

CatBoost uses **Ordered Boosting**: for each row, it only uses a model trained on PREVIOUS rows. This eliminates the bias and reduces overfitting.

#### 3. Symmetric Trees (Speed)

CatBoost builds **symmetric (balanced) decision trees** where the same splitting condition is used across an entire level. This makes predictions extremely fast because the CPU can use vectorized operations.

### How CatBoost Works in Our Project

```python
from catboost import CatBoostRegressor

model = CatBoostRegressor()
model.load_model('catboost_model.cbm')  # 33 MB model file
```

**Training process (done offline, model saved as catboost_model.cbm):**

```
Input Features (15 columns):
├── State (categorical → CatBoost handles natively)
├── District (categorical → CatBoost handles natively)  
├── Crop Year (numerical)
├── Season (categorical → CatBoost handles natively)
├── Crop Name (categorical → CatBoost handles natively)
├── Area in hectares (numerical)
├── Temperature (numerical)
├── Wind Speed (numerical)
├── Precipitation (numerical)
├── Humidity (numerical)
├── Soil Type (categorical → CatBoost handles natively)
├── Nitrogen N (numerical)
├── Phosphorus P (numerical)
├── Potassium K (numerical)
└── Pressure (numerical)

Target: Production in tons (numerical)
         ↓
    Log Transform: y = log(1 + production)
    (Because production is heavily skewed)
         ↓
    CatBoost trains 1000+ trees
         ↓
    Saved as: catboost_model.cbm (33 MB)
```

### The Log Transform — Why?

Production values range from 0 to millions of tons. A few mega-farms skew everything. Log transform compresses this:

```
Original:     1, 10, 100, 1000, 1000000
Log(1+x):     0.69, 2.4, 4.6, 6.9, 13.8
```

The model predicts in log-space, then we convert back:

```python
# In predict1() route:
pred_log = model.predict(features)[0]    # Model predicts log value
output = round(np.expm1(pred_log), 2)    # Convert back: e^pred - 1
```

`np.expm1(x)` = e^x - 1 (the inverse of `np.log1p(x)` = log(1+x))

### Label Encoding for Prediction

While CatBoost handles categories natively during TRAINING, for PREDICTION we need to convert user input text to the same numerical codes used during training:

```python
# Saved during training:
label_encoders = {
    'state_names': LabelEncoder fitted on all states,
    'district_names': LabelEncoder fitted on all districts,
    'season_names': LabelEncoder fitted on all seasons,
    'crop_names': LabelEncoder fitted on all crops,
    'soil_type': LabelEncoder fitted on all soil types
}

# During prediction:
state = label_encoders['state_names'].transform(["Tamil Nadu"])[0]  # → 28
district = label_encoders['district_names'].transform(["CHENNAI"])[0]  # → 45
```

---

## CHAPTER 7: THE PREDICTION FLOW

When a user fills the form and clicks "Predict Crop Yield":

```
User fills form:
  State: Tamil Nadu
  District: CHENNAI
  Year: 2025
  Season: Kharif
  Crop: Rice
  Area: 100
  Temperature: 30°C
  Wind: 2.5 m/s
  Precipitation: 800mm
  Humidity: 65%
  Soil: clay
  N: 50, P: 30, K: 25
  Pressure: 1010
        ↓
JavaScript sends POST to /predict1
        ↓
Flask receives form data
        ↓
Label Encoders convert text → numbers:
  "Tamil Nadu" → 28
  "CHENNAI" → 45
  "Kharif" → 2
  "Rice" → 85
  "clay" → 1
        ↓
Build feature vector:
  [28, 45, 2025, 2, 85, 100, 30, 2.5, 800, 65, 1, 50, 30, 25, 1010]
        ↓
CatBoost model predicts (in log space):
  pred_log = 8.52
        ↓
Convert back from log:
  output = e^8.52 - 1 = 5019.47 tons
        ↓
JSON response: {"prediction": "Estimated Production: 5019.47 tons"}
        ↓
JavaScript displays result on page
```
