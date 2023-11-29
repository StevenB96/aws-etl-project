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

class EtlProjectApp(Flask):
    def __init__(self, *args, **kwargs):
        super(EtlProjectApp, self).__init__(*args, **kwargs)
        self.setup()

    def setup(self):
        self.load_env()
        self.setup_routes()
        self.setup_logging()
        self.load_data_and_models()

    def load_env(self):
        # load_dotenv()
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.s3 = boto3.client('s3', aws_access_key_id=self.aws_access_key_id,
                               aws_secret_access_key=self.aws_secret_access_key)

    def load_data_and_models(self):
        # Load the input_data from the CSV file
        self.input_data = pd.read_csv(INPUT_DATA_PATH)

        # Load the models using joblib
        self.decision_tree_model = joblib.load(DECISION_TREE_MODEL_PATH)

    def setup_logging(self):
        handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=10000, backupCount=1)
        handler.setLevel(logging.ERROR)
        self.logger.addHandler(handler)

    def setup_routes(self):
        self.route('/template', methods=['GET'])(self.download_template)
        self.route('/upload', methods=['POST'])(self.upload_file)
        self.route('/search', methods=['GET'])(self.search)
        self.route('/predict', methods=['POST'])(self.predict)
        self.route('/')(self.index)
        self.route('/form')(self.index)

    def download_template(self):
        # Read CSV data from the file
        with open(TEMPLATE_FILE_PATH, 'r', newline='', encoding='utf-8') as file:
            csv_data = file.read()

        # Create a response with appropriate headers
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=template.csv'

        return response

    def upload_file(self):
        # self.load_env()
        error = None
        file_path = None  # Initialize file_path outside the try block

        try:
            # Check if 'csv' is present in the request.files
            if 'csv' not in request.files:
                raise Exception('No CSV file in the request')

            file = request.files['csv']

            # Check if the filename is empty
            if file.filename == '':
                raise Exception('The CSV file has no name')

            # Generate a timestamp for the filename
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

            # Append the timestamp to the original filename
            filename = timestamp + '_' + secure_filename(file.filename)
            file_path = os.path.join(UPLOADS_DIR, filename)

            # Save the file with the new filename
            file.save(file_path)

            # Upload the file to S3 using the new filename
            self.s3.upload_file(file_path, UPLOADS_BUCKET, filename)

        except Exception as e:
            error = str(e)
            # Add debug statement to print the exception
            print(f"Error during file upload: {error}")
        finally:
            # Add debug statement to print the file_path
            print(f"File path: {file_path}")

            # Remove the file if it exists
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

        # Add debug statement to print the error
        print(f"Upload error: {error}")

        # Return the rendered template with error information
        return render_template('form.html', error=self.aws_access_key_id)

    def search(self):
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

    def predict(self):
        # Extract input data from the POST request
        lead = float(request.form.get('lead'))
        director = float(request.form.get('director'))
        genre = float(request.form.get('genre'))
        budget = float(request.form.get('budget'))

        # Calculate artificial features
        matching_rows = self.input_data[(self.input_data['lead'] == lead)]
        lead_average_profit_ratio = matching_rows['profit_ratio'].mean()

        matching_rows = self.input_data[(self.input_data['director'] == director)]
        director_average_profit_ratio = matching_rows['profit_ratio'].mean()

        lead_worked_in_genre_count = self.input_data[
            (self.input_data['lead'] == lead) &
            (self.input_data['genre'] == genre)
        ].shape[0]

        director_worked_in_genre_count = self.input_data[
            (self.input_data['director'] == director) &
            (self.input_data['genre'] == genre)
        ].shape[0]

        director_worked_with_lead_count = self.input_data[
            (self.input_data['director'] == director) &
            (self.input_data['lead'] == lead)
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
        profit_ratio_prediction = self.decision_tree_model.predict(input)

        # Render the results using a template
        return render_template(
            'result.html',
            profit=f"${'{:,.0f}'.format(round((profit_ratio_prediction[0] * budget) - budget))}"
        )

    def index(self):
        return render_template('form.html')


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

app = EtlProjectApp(__name__)

if __name__ == '__main__':
    app.run(debug=True)
