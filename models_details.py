import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor  # Import Decision Tree
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score

def multiple_models(dataset_path):
    # Load the data
    df = pd.read_csv(dataset_path)
    
    # Drop unnecessary columns
    df.drop(['Unnamed: 0'], axis=1, inplace=True)
    
    # Define column names
    df.columns = ['State', 'District', 'Crop Year', 'Season', 'Crop Name',
                  'Area (hectares)', 'Temperature (°C)', 'Wind Speed (m/s)',
                  'Precipitation (mm)', 'Humidity (%)', 'Soil Type', 'Nitrogen (N)',
                  'Phosphorus (P)', 'Potassium (K)', 'Production (tons)', 'Pressure (hPa)']
    df["Production (tons)"] = pd.to_numeric(df["Production (tons)"], errors='coerce')

    # Check for any rows with NaN in 'Production (tons)'
    invalid_rows = df[df["Production (tons)"].isna()]

    # Drop rows with NaN in 'Production (tons)'
    df.dropna(subset=["Production (tons)"], inplace=True)
    
    # Extract object columns for encoding
    object_cols = df.select_dtypes(include='object').columns
    
    # Encode categorical columns
    mappings = {}
    for col in object_cols:
        unique_values = df[col].unique()
        mapping = {value: idx for idx, value in enumerate(unique_values)}
        mappings[col] = mapping
        df[col] = df[col].map(mapping)
    
    # Define input and output columns
    ind_col = [col for col in df.columns if col != "Production (tons)"]
    dep_col = "Production (tons)"
    
    X = df[ind_col]
    y = df[dep_col]
    
    # Split the data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.30, random_state=0)
    
    # Initialize models
    rf_model = RandomForestRegressor(random_state=0)
    xgb_model = DecisionTreeRegressor(random_state=0)  # Replaced XGBoost with Decision Tree
    lr_model = LinearRegression()
    
    # Train models and make predictions
    rf_model.fit(X_train, y_train)
    print("Random Forest model trained")
    
    xgb_model.fit(X_train, y_train)
    print("Decision Tree model (used in place of XGBoost) trained")
    
    lr_model.fit(X_train, y_train)
    print("Linear Regression model trained")
    
    # Predictions for each model
    rf_train_pred = rf_model.predict(X_train)
    rf_test_pred = rf_model.predict(X_test)
    
    xgb_train_pred = xgb_model.predict(X_train)
    xgb_test_pred = xgb_model.predict(X_test)
    
    lr_train_pred = lr_model.predict(X_train)
    lr_test_pred = lr_model.predict(X_test)
    
    # Calculate metrics
    results = {
        'random_forest': {
            'train_mse': mean_squared_error(y_train, rf_train_pred),
            'test_mse': mean_squared_error(y_test, rf_test_pred),
            'train_r2': r2_score(y_train, rf_train_pred),
            'test_r2': r2_score(y_test, rf_test_pred)
        },
        'xgboost': {  # This still refers to the Decision Tree model
            'train_mse': mean_squared_error(y_train, xgb_train_pred),
            'test_mse': mean_squared_error(y_test, xgb_test_pred),
            'train_r2': r2_score(y_train, xgb_train_pred),
            'test_r2': r2_score(y_test, xgb_test_pred)
        },
        'linear_regression': {
            'train_mse': mean_squared_error(y_train, lr_train_pred),
            'test_mse': mean_squared_error(y_test, lr_test_pred),
            'train_r2': r2_score(y_train, lr_train_pred),
            'test_r2': r2_score(y_test, lr_test_pred)
        }
    }
    
    return results

# Example usage:
# results = multiple_models('path_to_your_dataset.csv')
# print(results)
