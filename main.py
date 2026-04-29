# main.py

import os

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import random, pickle, numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')  # Add this line before importing pyplot
import matplotlib.pyplot as plt
import seaborn as sns
from import_analyse import basic_info, preprocess_data, eda_plots
from models_details import multiple_models
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from itsdangerous import URLSafeTimedSerializer
import secrets
from dotenv import load_dotenv
from pymongo import MongoClient

app = Flask(__name__)
load_dotenv()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# ================= MongoDB Atlas (IoT Sensor Data) =================
mongo_uri = os.getenv('MONGO_URI')
sensor_collection = None
if mongo_uri:
    try:
        mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        mongo_db = mongo_client['SoilDB']
        sensor_collection = mongo_db['SensorLogs']
        print('MongoDB connected successfully')
    except Exception as e:
        print(f'MongoDB connection failed: {e}')
        sensor_collection = None
else:
    print('MONGO_URI not set - IoT features disabled')


# ================= User Model =================
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================= Forms =================
class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=150)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    otp = StringField('OTP (if received)')
    submit = SubmitField('Login')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')


# ================= Routes =================

@app.route('/')
@login_required
def home():
    return render_template('home.html', title="Crop Yield Prediction Using Machine Learning")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: 
        return redirect(url_for('home'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first():
            flash('Username or email already exists.', 'danger')
        else:
            hashed_pw = generate_password_hash(form.password.data, method='pbkdf2:sha256')
            new_user = User(username=form.username.data, email=form.email.data, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            flash('Registered successfully. Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

import secrets
import time

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = LoginForm()
    show_otp = False

    if form.validate_on_submit():
        user = User.query.filter_by(
            username=form.username.data,
            email=form.email.data
        ).first()

        if not user:
            flash('User not found.', 'danger')
            return render_template('login.html', form=form, show_otp=show_otp)

        # STEP 1: Password entered, OTP not yet
        if form.password.data and not form.otp.data:

            if not check_password_hash(user.password, form.password.data):
                flash('Incorrect password.', 'danger')

            else:
                # Generate secure OTP
                otp = str(secrets.randbelow(900000) + 100000)

                # Store in session instead of DB
                session['otp'] = otp
                session['otp_user_id'] = user.id
                session['otp_expiry'] = time.time() + 300  # 5 min expiry

                try:
                    msg = Message(
                        'Your OTP Code',
                        sender=app.config['MAIL_USERNAME'],
                        recipients=[user.email]
                    )
                    msg.body = f"Your OTP is {otp}"
                    mail.send(msg)

                    flash('OTP sent. Enter OTP to complete login.', 'info')
                    show_otp = True

                except Exception as e:
                    flash(f'OTP email failed: {e}', 'danger')

        # STEP 2: OTP Verification
        elif form.otp.data:

            stored_otp = session.get('otp')
            otp_user_id = session.get('otp_user_id')
            otp_expiry = session.get('otp_expiry')

            if not stored_otp:
                flash('OTP session expired. Please login again.', 'danger')

            elif time.time() > otp_expiry:
                session.pop('otp', None)
                session.pop('otp_user_id', None)
                session.pop('otp_expiry', None)
                flash('OTP expired. Please login again.', 'danger')

            elif form.otp.data == stored_otp and user.id == otp_user_id:
                # Clear session OTP
                session.pop('otp', None)
                session.pop('otp_user_id', None)
                session.pop('otp_expiry', None)

                remember = True if request.form.get("remember") else False
                login_user(user, remember=remember)

                flash('Login successful!', 'success')
                return redirect(url_for('home'))

            else:
                flash('Invalid OTP.', 'danger')
                show_otp = True

    return render_template('login.html', form=form, show_otp=show_otp)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            token = serializer.dumps(user.email, salt='password-reset-salt')
            reset_link = url_for('reset_password', token=token, _external=True)

            msg = Message(
                'Password Reset Request',
                sender=app.config['MAIL_USERNAME'],
                recipients=[user.email]
            )
            msg.body = f'''To reset your password, click the link below:

{reset_link}

This link will expire in 10 minutes.
If you did not request this, ignore this email.
'''
            mail.send(msg)

        flash('If this email exists, a reset link has been sent.', 'info')
        return redirect(url_for('login'))

    return render_template('forgot_password.html', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(
            token,
            salt='password-reset-salt',
            max_age=600  # 10 minutes expiry
        )
    except:
        flash('The reset link is invalid or expired.', 'danger')
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('login'))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        user.password = hashed_pw
        db.session.commit()

        flash('Password reset successful. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html', form=form)


# ================= Lazy-Load Models and Data (avoids Gunicorn timeout) =================

from catboost import CatBoostRegressor

model = None
label_encoders = None
mappings = None
training_df = None
_models_loaded = False

def _load_models_and_data():
    """Load heavy models and CSV data on first request instead of at startup."""
    global model, label_encoders, mappings, training_df, _models_loaded
    if _models_loaded:
        return

    print('Loading CatBoost model...')
    model = CatBoostRegressor()
    model.load_model('catboost_model.cbm')
    print('CatBoost model loaded.')

    print('Loading label encoders...')
    with open('label_encoders.pkl', 'rb') as f:
        label_encoders = pickle.load(f)
    mappings = {col: dict(zip(le.classes_, le.transform(le.classes_)))
                for col, le in label_encoders.items()}
    print('Label encoders loaded.')

    print('Loading training dataset...')
    training_df = pd.read_csv('output.csv')
    print(f'Training dataset loaded: {len(training_df)} rows')

    _models_loaded = True

@app.before_request
def ensure_models_loaded():
    """Lazy-load models before the first real request."""
    _load_models_and_data()


def get_avg_rain_wind_by_area(area):
    """
    Returns average precipitation and wind_speed
    based on similar area values from training data
    """

    tolerance = 0.10  # ±10% area range
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


# ================= Prediction & Tools Routes =================

@app.route('/test_application')
@login_required
def test_application():
    return render_template(
        'recommendtrial.html',
        states=label_encoders['state_names'].classes_,
        districts=label_encoders['district_names'].classes_,
        seasons=label_encoders['season_names'].classes_,
        crops=label_encoders['crop_names'].classes_,
        soils=label_encoders['soil_type'].classes_
    )


@app.route('/predict1', methods=['POST'])
@login_required
def predict1():
    try:
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




@app.route('/get_avg_weather', methods=['POST'])
@login_required
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
@login_required
def get_districts():
    data = request.get_json()
    state = data.get('state')

    if not state:
        return jsonify([])

    # Filter using RAW STRING values
    districts = (
        training_df[training_df['state_names'] == state]
        ['district_names']
        .dropna()
        .unique()
        .tolist()
    )

    return jsonify(sorted(districts))


@app.route('/preprocessing_data')
@login_required
def preprocessing_data():
    num_nulls_before, cat_nulls_before, num_nulls_after, cat_nulls_after, head_html = preprocess_data('output.csv')
    return render_template('preprocessing_page.html', num_nulls_before=num_nulls_before,
                           cat_nulls_before=cat_nulls_before, num_nulls_after=num_nulls_after,
                           cat_nulls_after=cat_nulls_after, head=head_html)

@app.route('/eda_data')
@login_required
def eda_data():
    eda_plots('output.csv')
    return render_template('eda_page.html',
        numerical_dist_img='static/images/numerical_distribution.png',
        categorical_counts_img='static/images/categorical_counts.png',
        heatmap_img='static/images/heatmap.png')

@app.route('/eda_data2')
@login_required
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
@login_required
def models_data():
    results = multiple_models('output.csv')
    return render_template('models_dt.html', results=results)

@app.route('/disease-predict', methods=['GET', 'POST'])
@login_required
def disease_prediction():
    if request.method == 'POST':
        file = request.files.get('file')
        if file:
            file.save('output.csv')
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

    msg = Message(
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

    try:
        mail.send(msg)
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        return jsonify({"success": False}), 500


# ================= IoT Sensor Data API =================

@app.route('/api/iot-data')
@login_required
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
    # Simple API key check
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

        # Insert sensor reading into MongoDB
        from datetime import datetime
        data['timestamp'] = datetime.utcnow()
        sensor_collection.insert_one(data)
        return jsonify({"status": "ok", "message": "Data stored"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Create database tables (runs under both Gunicorn and direct execution)
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)