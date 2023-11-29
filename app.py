import pandas as pd
import os
from flask import Flask, render_template, request, make_response
import joblib
from datetime import datetime
from werkzeug.utils import secure_filename
import logging
from logging.handlers import RotatingFileHandler
import boto3
from io import StringIO
from env import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY


class EtlProjectApp(Flask):
    def __init__(self, *args, **kwargs):
        super(EtlProjectApp, self).__init__(*args, **kwargs)
        self.setup()

    def setup(self):
        self.load_env()
        self.initialise_constants()
        self.setup_routes()
        self.setup_logging()
        self.download_processed_data()
        self.load_model()

    def load_env(self):
        self.aws_access_key_id = AWS_ACCESS_KEY_ID
        self.aws_secret_access_key = AWS_SECRET_ACCESS_KEY
        self.s3 = boto3.client('s3', aws_access_key_id=self.aws_access_key_id,
                               aws_secret_access_key=self.aws_secret_access_key)

    def initialise_constants(self):
        # Define constants for S3 buckets and file names
        self.PROCESSED_BUCKET = 'etl-project-data-processed'
        self.UPLOADS_BUCKET = 'etl-project-uploads'
        self.INPUT_DATA_FILE = 'input_data.csv'
        self.UNIQUE_DIRECTORS_FILE = 'unique_directors.csv'
        self.UNIQUE_GENRES_FILE = 'unique_genres.csv'
        self.UNIQUE_LEADS_FILE = 'unique_leads.csv'
        self.CURRENT_DIR = os.path.dirname(__file__)
        self.MODEL_DIR = os.path.join(self.CURRENT_DIR, 'ml_model')
        self.MODEL_FILE = 'decision_tree_model.pkl'
        self.LOG_FILE = 'app.log'
        self.LOG_FILE_PATH = os.path.join(self.CURRENT_DIR, self.LOG_FILE)
        self.TEMPLATE_FILE_PATH = os.path.join(
            self.CURRENT_DIR, 'template.csv')
        self.DECISION_TREE_MODEL_PATH = os.path.join(
            self.MODEL_DIR, self.MODEL_FILE)

        # Variables to keep .csv data in state
        self.meta_data_frame = None
        self.unique_leads_data_frame = None
        self.unique_directors_data_frame = None
        self.unique_genres_data_frame = None

    def load_model(self):
        # Load the models using joblib
        self.decision_tree_model = joblib.load(self.DECISION_TREE_MODEL_PATH)

    def download_csv_from_s3(self, bucket, key):
        # Download and read CSV content from S3
        file_content = self.s3.get_object(Bucket=bucket, Key=key)[
            'Body'].read().decode('utf-8')
        return pd.read_csv(StringIO(file_content))

    def download_processed_data(self):
        file_keys = [
            self.INPUT_DATA_FILE,
            self.UNIQUE_DIRECTORS_FILE,
            self.UNIQUE_GENRES_FILE,
            self.UNIQUE_LEADS_FILE,
        ]

        # Download and read CSV files into DataFrames
        for file_key in file_keys:
            data_frame = self.download_csv_from_s3(
                self.PROCESSED_BUCKET, file_key)

            # Assign DataFrames to state fields based on key
            if "input_data" in file_key:
                self.meta_data_frame = data_frame
            elif "unique_leads" in file_key:
                self.unique_leads_data_frame = data_frame
            elif "unique_directors" in file_key:
                self.unique_directors_data_frame = data_frame
            elif "unique_genres" in file_key:
                self.unique_genres_data_frame = data_frame

            print(f"Data frame created from s3: {file_key}")

    def setup_logging(self):
        handler = RotatingFileHandler(
            self.LOG_FILE_PATH, maxBytes=10000, backupCount=1)
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
        with open(self.TEMPLATE_FILE_PATH, 'r', newline='', encoding='utf-8') as file:
            csv_data = file.read()

        # Create a response with appropriate headers
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=template.csv'

        return response

    def upload_file(self):
        error = None

        try:
            # Check if 'csv' is present in the request.files
            if 'csv' not in request.files:
                raise Exception('Error: No CSV file in the request')

            file = request.files['csv']

            # Generate a timestamp for the filename
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

            # Append the timestamp to the original filename
            filename = timestamp + '_' + secure_filename(file.filename)

            # Upload the file to S3 directly from the stream
            self.s3.upload_fileobj(file, self.UPLOADS_BUCKET, filename)

        except Exception as e:
            error = str(e)
            # Add debug statement to print the exception
            print(f"Error during file upload: {error}")

        # Return the rendered template with error information
        return render_template('form.html', error=error)

    def search(self):
        search_term = request.args.get('search_term')
        field_name = request.args.get('field_name')

        if (field_name and search_term):
            # Initialize data_list as an empty list
            data_list = []

            # Retrieve the appropriate data list based on field_name
            if field_name == 'lead':
                data_list = self.unique_leads_data_frame.to_dict(
                    orient='records')
            elif field_name == 'director':
                data_list = self.unique_directors_data_frame.to_dict(
                    orient='records')
            elif field_name == 'genre':
                data_list = self.unique_genres_data_frame.to_dict(
                    orient='records')

            filtered_items = [item for item in data_list if item.get(
                field_name, "").lower().startswith(search_term.lower()) if field_name in item]

            return {'results': filtered_items}

        return {'results': []}

    def predict(self):
        # Shortened name for self.uploads_data_frames
        meta_df = self.meta_data_frame

        # Extract input data from the POST request
        lead = float(request.form.get('lead'))
        director = float(request.form.get('director'))
        genre = float(request.form.get('genre'))
        budget = float(request.form.get('budget'))

        # Calculate artificial features
        matching_rows = meta_df[(meta_df['lead'] == lead)]
        lead_average_profit_ratio = matching_rows['profit_ratio'].mean()

        matching_rows = meta_df[(
            meta_df['director'] == director)]
        director_average_profit_ratio = matching_rows['profit_ratio'].mean()

        lead_worked_in_genre_count = meta_df[
            (meta_df['lead'] == lead) &
            (meta_df['genre'] == genre)
        ].shape[0]

        director_worked_in_genre_count = meta_df[
            (meta_df['director'] == director) &
            (meta_df['genre'] == genre)
        ].shape[0]

        director_worked_with_lead_count = meta_df[
            (meta_df['director'] == director) &
            (meta_df['lead'] == lead)
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


if __name__ == '__main__':
    app = EtlProjectApp(__name__)
    app.run(debug=True)
