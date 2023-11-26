import pandas as pd
import os
from flask import Flask, render_template, request, make_response
import joblib
from datetime import datetime
from werkzeug.utils import secure_filename
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import boto3

load_dotenv()

# AWS Credentials
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id,
                  aws_secret_access_key=aws_secret_access_key)

# Constants
CURRENT_DIR = os.path.dirname(__file__)

DATASETS_DIR = os.path.join(CURRENT_DIR, 'datasets')
MODEL_DIR = os.path.join(CURRENT_DIR, 'ml_model')

UNIQUE_LEADS_FILE = 'unique_leads.csv'
UNIQUE_DIRECTORS_FILE = 'unique_directors.csv'
UNIQUE_GENRES_FILE = 'unique_genres.csv'
INPUT_DATA_FILE = 'input_data.csv'
MODEL_FILE = 'decision_tree_model.pkl'
LOG_FILE = 'app.log'

DECISION_TREE_MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILE)
UNIQUE_LEADS_PATH = os.path.join(DATASETS_DIR, UNIQUE_LEADS_FILE)
UNIQUE_DIRECTORS_PATH = os.path.join(DATASETS_DIR, UNIQUE_DIRECTORS_FILE)
UNIQUE_GENRES_PATH = os.path.join(DATASETS_DIR, UNIQUE_GENRES_FILE)
INPUT_DATA_PATH = os.path.join(DATASETS_DIR, INPUT_DATA_FILE)
LOG_FILE_PATH = os.path.join(CURRENT_DIR, LOG_FILE)

TEMPLATE_FILE_PATH = os.path.join(CURRENT_DIR, 'template.csv')
UPLOADS_DIR = os.path.join(CURRENT_DIR, 'uploads')

UPLOADS_BUCKET = 'etl-project-uploads'

if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)

app = Flask(__name__)

# Configure Flask app to log to a file
handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=10000, backupCount=1)
handler.setLevel(logging.ERROR)
app.logger.addHandler(handler)

# Load the input_data from the CSV file
input_data = pd.read_csv(INPUT_DATA_PATH)

# Load the models using joblib
decision_tree_model = joblib.load(DECISION_TREE_MODEL_PATH)


def generate_secure_filename(original_filename):
    # Use secure_filename to sanitize and secure the original filename
    secure_name = secure_filename(original_filename)
    return secure_name


@app.route('/template', methods=['GET'])
def download_template():
    # Read CSV data from the file
    with open(TEMPLATE_FILE_PATH, 'r', newline='', encoding='utf-8') as file:
        csv_data = file.read()

    # Create a response with appropriate headers
    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=template.csv'

    return response


@app.route('/upload', methods=['POST'])
def upload_file():
    error = None

    try:
        if 'csv' not in request.files:
            raise Exception('There was no CSV content')

        file = request.files['csv']

        if file.filename == '':
            raise Exception('The CSV file was unnamed')

        # Generate a timestamp for the filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        # Append the timestamp to the original filename
        filename = timestamp + '_' + secure_filename(file.filename)
        file_path = os.path.join(UPLOADS_DIR, filename)

        # Save the file with the new filename
        file.save(file_path)

        # Upload the file to S3 using the new filename
        s3.upload_file(file_path, UPLOADS_BUCKET, filename)

        # Clear local file
        os.remove(file_path)        
    except Exception as e:
        error = e

    return render_template('form.html', error=error)


@app.route('/search', methods=['GET'])
def search():
    search_term = request.args.get('search_term')
    field_name = request.args.get('field_name')

    if (field_name and search_term):
        # Initialize data_list as an empty list
        data_list = []

        # Retrieve the appropriate data list based on field_name
        if field_name == 'lead':
            unique_leads = pd.read_csv(UNIQUE_LEADS_PATH)
            data_list = unique_leads.to_dict(orient='records')
        elif field_name == 'director':
            unique_directors = pd.read_csv(
                UNIQUE_DIRECTORS_PATH)
            data_list = unique_directors.to_dict(orient='records')
        elif field_name == 'genre':
            unique_genres = pd.read_csv(UNIQUE_GENRES_PATH)
            data_list = unique_genres.to_dict(orient='records')

        filtered_items = [item for item in data_list if item.get(
            field_name, "").lower().startswith(search_term.lower()) if field_name in item]

        return {'results': filtered_items}

    return {'results': []}


@app.route('/predict', methods=['POST'])
def predict():
    # Extract input data from the POST request
    lead = float(request.form.get('lead'))
    director = float(request.form.get('director'))
    genre = float(request.form.get('genre'))
    budget = float(request.form.get('budget'))

    # Calculate artificial features
    matching_rows = input_data[(input_data['lead'] == lead)]
    lead_average_profit_ratio = matching_rows['profit_ratio'].mean()

    matching_rows = input_data[(input_data['director'] == director)]
    director_average_profit_ratio = matching_rows['profit_ratio'].mean()

    lead_worked_in_genre_count = input_data[
        (input_data['lead'] == lead) &
        (input_data['genre'] == genre)
    ].shape[0]

    director_worked_in_genre_count = input_data[
        (input_data['director'] == director) &
        (input_data['genre'] == genre)
    ].shape[0]

    director_worked_with_lead_count = input_data[
        (input_data['director'] == director) &
        (input_data['lead'] == lead)
    ].shape[0]

    # Create an input array for prediction
    input = [[
        budget,
        director_average_profit_ratio,
        lead_average_profit_ratio,
        lead_worked_in_genre_count,
        director_worked_in_genre_count,
        director_worked_with_lead_count,
    ]]

    # Make predictions using the decision tree model
    profit_ratio_prediction = decision_tree_model.predict(input)

    # Render the results using a template
    return render_template(
        'result.html',
        profit=f"${'{:,.0f}'.format(round((profit_ratio_prediction[0] * budget) - budget))}"
    )


@app.route('/')
@app.route('/form')
def index():
    return render_template('form.html')


if __name__ == '__main__':
    # host='0.0.0.0', port=5000,
    app.run(debug=True)
