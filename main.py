# main.py — Auth removed, all heavy imports deferred for Render free tier

import os
import pickle
import gc

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-fallback-key')

# ================= MongoDB Atlas (IoT Sensor Data) =================
mongo_uri = os.getenv('MONGO_URI')
sensor_collection = None
if mongo_uri:
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        mongo_db = mongo_client['SoilDB']
        sensor_collection = mongo_db['SensorLogs']
        print('MongoDB connected successfully')
    except Exception as e:
        print(f'MongoDB connection failed: {e}')
        sensor_collection = None
else:
    print('MONGO_URI not set - IoT features disabled')


# ================= Lazy-Load Models and Data =================

model = None
label_encoders = None
mappings = None
training_df = None
_encoders_loaded = False
_heavy_models_loaded = False

# Routes that do NOT need any ML models
_SKIP_ALL_LOAD = {'home', 'static', 'send_contact', 'iot_upload'}

def _load_encoders():
    """Load only label encoders (tiny, fast ~10KB)."""
    global label_encoders, mappings, _encoders_loaded
    if _encoders_loaded:
        return
    print('Loading label encoders...')
    with open('label_encoders.pkl', 'rb') as f:
        label_encoders = pickle.load(f)
    mappings = {col: dict(zip(le.classes_, le.transform(le.classes_)))
                for col, le in label_encoders.items()}
    print('Label encoders loaded.')
    _encoders_loaded = True

def _load_heavy_models():
    """Load CatBoost model and CSV data (heavy)."""
    global model, training_df, _heavy_models_loaded
    if _heavy_models_loaded:
        return

    _load_encoders()

    import numpy as np
    import pandas as pd
    from catboost import CatBoostRegressor

    print('Loading CatBoost model...')
    model = CatBoostRegressor()
    model.load_model('catboost_model.cbm')
    print('CatBoost model loaded.')

    print('Loading training dataset (selected columns only)...')
    needed_cols = ['state_names', 'district_names', 'area', 'precipitation', 'wind_speed']
    training_df = pd.read_csv('output.csv', usecols=needed_cols)
    print(f'Training dataset loaded: {len(training_df)} rows, {len(needed_cols)} columns')

    gc.collect()
    _heavy_models_loaded = True

@app.before_request
def ensure_models_loaded():
    """Load only what's needed based on the requested route."""
    endpoint = request.endpoint
    if endpoint in _SKIP_ALL_LOAD or endpoint is None:
        return
    if endpoint in ('predict1', 'get_avg_weather', 'get_districts',
                     'get_iot_data'):
        _load_heavy_models()
    elif endpoint in ('preprocessing_data', 'eda_data', 'models_data',
                       'disease_prediction'):
        pass  # These routes import their own heavy modules inline


# ================= Routes =================

@app.route('/')
def home():
    return render_template('home.html', title="Crop Yield Prediction Using Machine Learning")


# ================= Prediction & Tools Routes =================

@app.route('/test_application')
def test_application():
    _load_encoders()
    # Start loading heavy models in background while user fills the form
    if not _heavy_models_loaded:
        import threading
        threading.Thread(target=_load_heavy_models, daemon=True).start()
    return render_template(
        'recommendtrial.html',
        states=label_encoders['state_names'].classes_,
        districts=label_encoders['district_names'].classes_,
        seasons=label_encoders['season_names'].classes_,
        crops=label_encoders['crop_names'].classes_,
        soils=label_encoders['soil_type'].classes_
    )


@app.route('/predict1', methods=['POST'])
def predict1():
    try:
        import numpy as np
        data = request.form

        # Encode categorical inputs using saved LabelEncoders
        state = label_encoders['state_names'].transform([data['state_name']])[0]
        district = label_encoders['district_names'].transform([data['district_name']])[0]
        season = label_encoders['season_names'].transform([data['season_name']])[0]
        crop = label_encoders['crop_names'].transform([data['crop_name']])[0]
        soil = label_encoders['soil_type'].transform([data['soil_type']])[0]

        # Build feature vector (order must match training columns)
        features = np.array([[
            state,
            district,
            int(data['crop_year']),
            season,
            crop,
            float(data['area']),
            float(data['temperature']),
            float(data['wind_speed']),
            float(data['precipitation']),
            float(data['humidity']),
            soil,
            float(data['N']),
            float(data['P']),
            float(data['K']),
            float(data['pressure'])
        ]])

        # Predict (trained with log transform → inverse here)
        pred_log = model.predict(features)[0]
        output = round(np.expm1(pred_log), 2)

        return jsonify({
                "prediction": f"Estimated Production: {output} tons"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


def get_avg_rain_wind_by_area(area):
    """
    Returns average precipitation and wind_speed
    based on similar area values from training data
    """
    tolerance = 0.10
    min_area = area * (1 - tolerance)
    max_area = area * (1 + tolerance)

    filtered_df = training_df[
        (training_df['area'] >= min_area) &
        (training_df['area'] <= max_area)
    ]

    if filtered_df.empty:
        avg_rainfall = training_df['precipitation'].mean()
        avg_wind_speed = training_df['wind_speed'].mean()
    else:
        avg_rainfall = filtered_df['precipitation'].mean()
        avg_wind_speed = filtered_df['wind_speed'].mean()

    return round(avg_rainfall, 2), round(avg_wind_speed, 2)


@app.route('/get_avg_weather', methods=['POST'])
def get_avg_weather():
    data = request.get_json()
    state = data.get('state')
    district = data.get('district')

    if not state or not district:
        return jsonify({"error": "State and district are required"}), 400

    filtered_df = training_df[
        (training_df['state_names'] == state) &
        (training_df['district_names'] == district)
    ]

    if filtered_df.empty:
        avg_rainfall = training_df['precipitation'].mean()
        avg_wind_speed = training_df['wind_speed'].mean()
    else:
        avg_rainfall = filtered_df['precipitation'].mean()
        avg_wind_speed = filtered_df['wind_speed'].mean()

    return jsonify({
        'avg_rainfall': round(avg_rainfall, 2),
        'avg_wind_speed': round(avg_wind_speed, 2)
    })


@app.route('/get_districts', methods=['POST'])
def get_districts():
    data = request.get_json()
    state = data.get('state')

    if not state:
        return jsonify([])

    districts = (
        training_df[training_df['state_names'] == state]
        ['district_names']
        .dropna()
        .unique()
        .tolist()
    )

    return jsonify(sorted(districts))


@app.route('/preprocessing_data')
def preprocessing_data():
    from import_analyse import preprocess_data
    num_nulls_before, cat_nulls_before, num_nulls_after, cat_nulls_after, head_html = preprocess_data('output.csv')
    return render_template('preprocessing_page.html', num_nulls_before=num_nulls_before,
                           cat_nulls_before=cat_nulls_before, num_nulls_after=num_nulls_after,
                           cat_nulls_after=cat_nulls_after, head=head_html)

@app.route('/eda_data')
def eda_data():
    from import_analyse import eda_plots
    eda_plots('output.csv')
    return render_template('eda_page.html',
        numerical_dist_img='static/images/numerical_distribution.png',
        categorical_counts_img='static/images/categorical_counts.png',
        heatmap_img='static/images/heatmap.png')

@app.route('/eda_data2')
def eda_data2():
    return render_template('eda_page2.html',
        numerical_dist_img='static/images/production_violin_plot.png',
        categorical_counts_img='static/images/area_vs_production_scatter_plot.png',
        heatmap_img='static/images/area_vs_production_line_plot.png',
        heatmap_img2='static/images/temperature_vs_production_line_plot.png',
        heatmap_img3='static/images/rainfall_vs_production_line_plot.png')


@app.route('/disease-predict2', methods=['GET', 'POST'])
def disease_prediction2():
    title = 'Crop Yield Prediction Using Machine Learning'
    return render_template('rust.html', title=title)

@app.route('/dataprep', methods=['GET', 'POST'])
def dataprep():
    title = 'Crop Yield Prediction Using Machine Learning'
    return render_template('rust.html', title=title)

@app.route('/models_data')
def models_data():
    from models_details import multiple_models
    results = multiple_models('output.csv')
    return render_template('models_dt.html', results=results)

@app.route('/disease-predict', methods=['GET', 'POST'])
def disease_prediction():
    if request.method == 'POST':
        file = request.files.get('file')
        if file:
            file.save('output.csv')
            from import_analyse import basic_info
            head, shape, describe, info = basic_info('output.csv')
            return render_template('rust-result.html', head=head, shape=shape, describe=describe, info=info)
        else:
            flash("Please upload a valid file.", "warning")
            return redirect(request.url)
    return render_template('disease_predict.html')


@app.route("/send_contact", methods=["POST"])
def send_contact():
    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    subject = data.get("subject")
    message = data.get("message")

    if not all([name, email, subject, message]):
        return jsonify({"success": False, "error": "Missing fields"}), 400

    try:
        from flask_mail import Mail, Message as MailMessage
        mail = Mail(app)
        app.config['MAIL_SERVER'] = 'smtp.gmail.com'
        app.config['MAIL_PORT'] = 587
        app.config['MAIL_USE_TLS'] = True
        app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
        app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
        mail.init_app(app)

        msg = MailMessage(
            subject=f"[Farmsight Contact] {subject}",
            sender=app.config['MAIL_USERNAME'],
            recipients=["sunharshini@gmail.com"],
            body=f"""
    Name: {name}
    Email: {email}

    Message:
    {message}
    """
        )
        mail.send(msg)
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        return jsonify({"success": False}), 500


# ================= IoT Sensor Data API =================

@app.route('/api/iot-data')
def get_iot_data():
    """Fetch the latest IoT sensor reading from MongoDB and return as JSON.
    Converts temperature from Fahrenheit to Celsius."""
    if sensor_collection is None:
        return jsonify({"error": "IoT not configured (MONGO_URI missing)"}), 503

    try:
        latest = sensor_collection.find_one(
            sort=[("_id", -1)]  # Most recent document
        )
        if latest:
            # Convert Fahrenheit to Celsius
            temp_f = latest.get("tempF", 0)
            temp_c = round((temp_f - 32) * 5.0 / 9.0, 2)

            return jsonify({
                "temperature": temp_c,
                "humidity": latest.get("humidity"),
                "pressure": latest.get("pressure"),
                "N": latest.get("N"),
                "P": latest.get("P"),
                "K": latest.get("K"),
                "timestamp": str(latest.get("_id").generation_time),
                "source": "IoT Sensor (ESP32)"
            })
        return jsonify({"error": "No sensor data available yet"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/iot-upload', methods=['POST'])
def iot_upload():
    """Receive sensor data from ESP32 and store in MongoDB.
    ESP32 sends JSON with: tempF, humidity, pressure, N, P, K
    Secured with a simple API key in the header."""
    api_key = request.headers.get('X-API-Key', '')
    expected_key = os.getenv('IOT_API_KEY', 'farmsight-iot-2026')
    if api_key != expected_key:
        return jsonify({"error": "Unauthorized"}), 401

    if sensor_collection is None:
        return jsonify({"error": "MongoDB not configured"}), 503

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        from datetime import datetime
        data['timestamp'] = datetime.utcnow()
        sensor_collection.insert_one(data)
        return jsonify({"status": "ok", "message": "Data stored"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)