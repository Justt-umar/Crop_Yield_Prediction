# necessary imports 
 
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg') 
import seaborn as sns
import plotly.express as px
import io
import warnings
warnings.filterwarnings('ignore')

plt.style.use('fivethirtyeight')
#%matplotlib inline
pd.set_option('display.max_columns', 26)


def basic_info(file_path):
    # Load the CSV file into a DataFrame 
    df = pd.read_csv(file_path)
    
    # Drop any unnamed columns that might have been added during saving (if applicable)
    df.drop('Unnamed: 0', axis=1, inplace=True, errors='ignore')
    
    # Update the column names to reflect the new dataset structure
    df.columns = ['State', 'District', 'Crop Year', 'Season', 'Crop Name', 
                  'Area (hectares)', 'Temperature (°C)', 'Wind Speed (m/s)', 
                  'Precipitation (mm)', 'Humidity (%)', 'Soil Type', 'Nitrogen (N)',
                  'Phosphorus (P)', 'Potassium (K)', 'Production (tons)', 'Pressure (hPa)']
    
    # Convert the DataFrame's head (first few rows) to HTML for display
    head_html = df.head().to_html(classes='table table-striped')
    
    # Generate descriptive statistics for the DataFrame (excluding categorical columns)
    describe_html = df.describe().to_html(classes='table table-striped')
    
    # Get the shape (dimensions) of the DataFrame
    shape = df.shape
    
    # Capture DataFrame info in a buffer and convert it to HTML format
    info_buf = io.StringIO()
    df.info(buf=info_buf)
    info_html = info_buf.getvalue().replace('\n', '<br>')
    
    return head_html, shape, describe_html, info_html

def preprocess_data(file_path):
    # Load the CSV file into a DataFrame
    df = pd.read_csv(file_path)
    
    # Drop any unnamed columns that might have been added during saving (if applicable)
    df.drop('Unnamed: 0', axis=1, inplace=True, errors='ignore')
    
    # Update the column names to reflect the new dataset structure
    df.columns = ['State', 'District', 'Crop Year', 'Season', 'Crop Name', 
                  'Area (hectares)', 'Temperature (°C)', 'Wind Speed (m/s)', 
                  'Precipitation (mm)', 'Humidity (%)', 'Soil Type', 'Nitrogen (N)',
                  'Phosphorus (P)', 'Potassium (K)', 'Production (tons)', 'Pressure (hPa)']
    
    # Separate categorical and numerical columns
    cat_cols = [col for col in df.columns if df[col].dtype == 'object']
    num_cols = [col for col in df.columns if df[col].dtype != 'object']
    
    # Record the number of null values before imputation
    num_nulls_before = df[num_cols].isnull().sum().to_dict()
    cat_nulls_before = df[cat_cols].isnull().sum().to_dict()
    
    # Function for random value imputation on numerical columns
    def random_value_imputation(feature):
        random_sample = df[feature].dropna().sample(df[feature].isna().sum())
        random_sample.index = df[df[feature].isnull()].index
        df.loc[df[feature].isnull(), feature] = random_sample

    # Function for imputing missing categorical values using mode
    def impute_mode(feature):
        mode = df[feature].mode()[0]
        df[feature] = df[feature].fillna(mode)
    
    # Apply random value imputation for all numerical columns
    for col in num_cols:
        random_value_imputation(col)
    
    # Apply mode imputation for all categorical columns
    for col in cat_cols:
        impute_mode(col)
    
    # Record the number of null values after imputation
    num_nulls_after = df[num_cols].isnull().sum().to_dict()
    cat_nulls_after = df[cat_cols].isnull().sum().to_dict()
    
    # Return the null value summaries before and after, and the first few rows of the dataframe
    return (num_nulls_before, cat_nulls_before, num_nulls_after, cat_nulls_after, df.head().to_html(classes='table table-striped'))
def violin_plot(col, df):
    # Violin plot comparing 'Production' with the chosen column
    fig = px.violin(df, y=col, x="Production (tons)", color="Production (tons)", box=True, template='plotly_dark')
    return fig.to_html(full_html=False)

def kde_plot(col, df):
    # KDE plot comparing 'Production' with the chosen column
    plt.figure(figsize=(10, 6))
    grid = sns.FacetGrid(df, hue="Production (tons)", height=6, aspect=2)
    grid.map(sns.kdeplot, col)
    grid.add_legend()
    plt.tight_layout()
    plt.savefig('static/images/kde_plot.png')  # Save plot as an image file
    return plt.gcf().canvas.get_supported_filetypes()['png']

def scatter_plot(col1, col2, df):
    # Scatter plot comparing two columns with 'Production' as the color
    fig = px.scatter(df, x=col1, y=col2, color="Production (tons)", template='plotly_dark')
    return fig.to_html(full_html=False)


def eda_plots(file_path):
    # Load the CSV file into a DataFrame
    df = pd.read_csv(file_path)
    df=df.head(2000)
    df.drop('Unnamed: 0', axis=1, inplace=True, errors='ignore')
    
    # Update column names
    df.columns = ['State', 'District', 'Crop Year', 'Season', 'Crop Name', 
                  'Area (hectares)', 'Temperature (°C)', 'Wind Speed (m/s)', 
                  'Precipitation (mm)', 'Humidity (%)', 'Soil Type', 'Nitrogen (N)',
                  'Phosphorus (P)', 'Potassium (K)', 'Production (tons)', 'Pressure (hPa)']

    # Separate categorical and numerical columns
    cat_cols = [col for col in df.columns if df[col].dtype == 'object']
    num_cols = [col for col in df.columns if df[col].dtype != 'object']

    # Numerical features distribution
    plt.figure(figsize=(20, 15))
    plotnumber = 1
    for column in num_cols:
        if plotnumber <= len(num_cols):  # Dynamically adjust to number of numerical columns
            ax = plt.subplot(3, 5, plotnumber)
            sns.histplot(df[column], kde=True)  # Replacing distplot with histplot as distplot is deprecated
            plt.xlabel(column)
        plotnumber += 1
    plt.tight_layout()
    plt.savefig('static/images/numerical_distribution.png')  # Save the plot as an image
    plt.close()
    print("one type plots saved")

    # Categorical columns count plot
    plt.figure(figsize=(20, 15))
    plotnumber = 1
    for column in cat_cols:
        if plotnumber <= len(cat_cols):  # Dynamically adjust to number of categorical columns
            ax = plt.subplot(3, 4, plotnumber)
            sns.countplot(x=df[column], palette='rocket')
            plt.xlabel(column)
        plotnumber += 1
    plt.tight_layout()
    plt.savefig('static/images/categorical_counts.png')  # Save the plot as an image
    plt.close()
    print("two type plots saved")
    # Heatmap of correlations between numerical columns
    # Heatmap of correlations between only numeric columns
    plt.figure(figsize=(15, 8))
    numeric_df = df.select_dtypes(include=[np.number])  # ✅ Only numeric columns
    corr_matrix = numeric_df.corr()
    sns.heatmap(corr_matrix, annot=True, linewidths=2, linecolor='lightgrey', cmap='coolwarm')
    plt.tight_layout()
    plt.savefig('static/images/heatmap.png')  # Save the plot as an image
    plt.close()

