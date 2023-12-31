import logging
import os
import boto3
import joblib
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import io
import base64

from logging.handlers import RotatingFileHandler
from datetime import datetime
from io import BytesIO, StringIO
from flask import (Flask, make_response, redirect, render_template, request,
                   url_for)
from scipy.stats import norm, percentileofscore
from werkzeug.utils import secure_filename

from env import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY


class EtlProjectApp(Flask):
    def __init__(self, *args, **kwargs):
        super(EtlProjectApp, self).__init__(*args, **kwargs)
        self.setup()

    def setup(self):
        self.load_env()
        self.initialise_constants()
        self.setup_routes()
        # self.setup_logging()
        self.download_processed_data()
        self.download_model_from_s3()

    def load_env(self):
        self.aws_access_key_id = AWS_ACCESS_KEY_ID
        self.aws_secret_access_key = AWS_SECRET_ACCESS_KEY
        self.s3 = boto3.client('s3', aws_access_key_id=self.aws_access_key_id,
                               aws_secret_access_key=self.aws_secret_access_key)

    def initialise_constants(self):
        # Define constants for S3 buckets and file names
        self.PROCESSED_BUCKET = 'etl-project-data-processed'
        self.UPLOADS_BUCKET = 'etl-project-uploads'
        self.MODEL_BUCKET = 'etl-project-ml-model'
        self.INPUT_DATA_FILE = 'input_data.csv'
        self.UNIQUE_DIRECTORS_FILE = 'unique_directors.csv'
        self.UNIQUE_GENRES_FILE = 'unique_genres.csv'
        self.UNIQUE_LEADS_FILE = 'unique_leads.csv'
        self.CURRENT_DIR = os.path.dirname(__file__)
        self.MODEL_FILE = 'decision_tree_model.pkl'
        self.LOG_FILE = 'app.log'
        self.LOG_FILE_PATH = os.path.join(self.CURRENT_DIR, self.LOG_FILE)
        self.TEMPLATE_FILE_PATH = os.path.join(
            self.CURRENT_DIR, 'template.csv')

        # Variables to keep .csv data in state
        self.meta_data_frame = None
        self.unique_leads_data_frame = None
        self.unique_directors_data_frame = None
        self.unique_genres_data_frame = None
        self.decision_tree_model = None

    def download_model_from_s3(self):
        # Download the model file from S3
        model_file_content = self.s3.get_object(
            Bucket=self.MODEL_BUCKET, Key=self.MODEL_FILE)['Body'].read()

        # Load the model from the downloaded content
        self.decision_tree_model = joblib.load(BytesIO(model_file_content))

        print(f"Model downloaded from S3: {self.MODEL_FILE}")

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
        handler.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

    def setup_routes(self):
        self.route('/template', methods=['GET'])(self.download_template)
        self.route('/upload', methods=['POST'])(self.upload_file)
        self.route('/search', methods=['GET'])(self.search)
        self.route('/predict', methods=['POST'])(self.predict)
        self.route('/')(self.index)
        self.route('/<path:catch_all>', methods=['GET'])(self.catch_all_route)

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
        return render_template('main.html', error=error)

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

    def plot_score(self, score):
        matplotlib.use('Agg')

        # Set the mean and standard deviation for the normal distribution
        mean = 0
        std_dev = 1
        data_points = 100

        # Generate random numbers from a normal distribution
        data = np.random.normal(mean, std_dev, data_points)

        # Fit a normal distribution to the data
        fit_mean, fit_std = norm.fit(data)

        bins = max(10, round(data_points / 20))

        # Plot the histogram of the random numbers
        plt.hist(data, bins=bins, density=True, alpha=0.5, color='#007bff')

        # Overlay a normal distribution curve
        xmin, xmax = plt.xlim()
        x = np.linspace(xmin, xmax, 100)
        p = norm.pdf(x, fit_mean, fit_std)
        plt.plot(x, p, 'k', linewidth=2)

        # Add vertical lines to represent percentiles
        percentiles = [25, 50, 75]
        percentile_values = np.percentile(data, percentiles)
        for percentile, value in zip(percentiles, percentile_values):
            plt.axvline(value, color='black', linestyle='dashed', linewidth=1)

        # Add a vertical line to represent a specific value (e.g., x=2)
        plt.axvline(score, color='#007bff', linestyle='solid',
                    linewidth=2, label=f'Your score')

        # Calculate and display the percentile of the specific value
        score_percentile = percentileofscore(data, score)
        plt.title(f'Score Distribution')

        # Add labels and title
        plt.xlabel('Value')
        plt.ylabel('Probability Density')

        # Add legend
        plt.legend()

        # Save the plot as a PNG in memory
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)

        # Convert the image data to a base64-encoded string
        image_string = base64.b64encode(buffer.read()).decode('utf-8')

        # Close the buffer to free up resources
        buffer.close()

        plt.clf()

        return image_string, score_percentile

    def predict(self):
        # Shortened name for self.uploads_data_frames
        meta_df = self.meta_data_frame

        # Extract input data from the POST request
        data = request.get_json()
        lead = float(data.get('lead'))
        director = float(data.get('director'))
        genre = float(data.get('genre'))
        budget = float(data.get('budget'))

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

        image_string, score_percentile = self.plot_score(
            profit_ratio_prediction)

        profit = round((profit_ratio_prediction[0] * budget) - budget)

        return {
            'profit': "${:,.2f}".format(profit),
            'score_percentile': tuple(score_percentile)[0],
            'image_string': image_string
        }

    def catch_all_route(self, catch_all):
        return render_template('main.html')

    def index(self):
        return render_template('main.html')


app = EtlProjectApp(__name__)

if __name__ == '__main__':
    app.logger.setLevel(logging.DEBUG)
    app.run(debug=True)
