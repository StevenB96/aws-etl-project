import pandas as pd
from functools import reduce
import boto3
from env import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
from io import StringIO


class ETLProcessor:
    def __init__(self):
        self.load_env()
        self.initialise_constants()

    def load_env(self):
        # Load AWS credentials from environment
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

        # Variables to keep .csv data in state
        self.meta_data_frame = None
        self.unique_leads_data_frame = None
        self.unique_directors_data_frame = None
        self.unique_genres_data_frame = None
        self.uploads_data_frames = None

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

            print(f"Dataframe created from s3: {file_key}")

    def download_uploads(self):
        objects = self.s3.list_objects(Bucket=self.UPLOADS_BUCKET)
        file_keys = [obj['Key'] for obj in objects.get('Contents', [])]

        # Download and read CSV files into DataFrames
        uploads_data_frames = []

        for file_key in file_keys:
            data_frame = self.download_csv_from_s3(
                self.UPLOADS_BUCKET, file_key)

            # Append the DataFrame to the list
            uploads_data_frames.append(data_frame)

            print(f"Dataframe created from s3: {file_key}")

        if not uploads_data_frames:
            return

        # Concatenate all DataFrames into a single DataFrame
        self.uploads_data_frames = pd.concat(
            uploads_data_frames, ignore_index=True)

    def upload_dataframe_to_s3(self, data_frame, bucket, key):
        # Convert DataFrame to CSV content
        csv_content = data_frame.to_csv(index=False)

        # Upload CSV content to S3
        self.s3.put_object(Body=csv_content, Bucket=bucket, Key=key)
        print(f"DataFrame uploaded to S3: {key}")

    def upload_processed_data_to_s3(self):
        data_frames_to_upload = {
            self.INPUT_DATA_FILE: self.meta_data_frame,
            self.UNIQUE_LEADS_FILE: self.unique_leads_data_frame,
            self.UNIQUE_DIRECTORS_FILE: self.unique_directors_data_frame,
            self.UNIQUE_GENRES_FILE: self.unique_genres_data_frame,
        }

        for file_key, data_frame in data_frames_to_upload.items():
            self.upload_dataframe_to_s3(
                data_frame, self.PROCESSED_BUCKET, file_key)

    def clear_upload_data(self):
        objects = self.s3.list_objects(Bucket=self.UPLOADS_BUCKET)

        for obj in objects.get('Contents', []):
            file_key = obj['Key']
            self.s3.delete_object(Bucket=self.UPLOADS_BUCKET, Key=file_key)
            print(f"File deleted from S3: {file_key}")

    def filter_uploads(self):
        # Shortened name for self.uploads_data_frames
        uploads_df = self.uploads_data_frames

        # Define the expected columns that should be present in the DataFrames
        expected_columns = ['title', 'lead',
                            'director', 'genre', 'revenue', 'budget']

        # Filter DataFrame rows based on expected columns
        uploads_df = uploads_df[
            uploads_df.apply(lambda row: all(col in row.index for col in expected_columns) and len(
                row.index) == len(expected_columns), axis=1)
        ].drop_duplicates(subset='title').reset_index(drop=True)

        # Convert 'budget' and 'revenue' columns to integers if possible
        uploads_df['budget'] = pd.to_numeric(
            uploads_df['budget'], errors='coerce')
        uploads_df['revenue'] = pd.to_numeric(
            uploads_df['revenue'], errors='coerce')

        # Get the min and max values for budget and revenue from the meta_data_frame
        max_budget, min_budget = self.meta_data_frame['budget'].max(
        ), self.meta_data_frame['budget'].min()
        max_revenue, min_revenue = self.meta_data_frame['revenue'].max(
        ), self.meta_data_frame['revenue'].min()

        # Filter the uploads_data_frames based on budget and revenue thresholds
        uploads_df = uploads_df[
            (uploads_df['budget'] < max_budget) &
            (uploads_df['budget'] > min_budget) &
            (uploads_df['revenue'] < max_revenue) &
            (uploads_df['revenue'] > min_revenue)
        ]

        # Remove duplicates based on the 'title' column and reset the index
        self.uploads_data_frames = uploads_df[
            ~uploads_df['title'].isin(self.meta_data_frame['title'])
        ]

    def merge_in_type_definitions(self):
        # Loop through the columns and corresponding data frames
        for column, type_df in (
                ("director", self.unique_directors_data_frame),
                ("genre", self.unique_genres_data_frame),
                ("lead", self.unique_leads_data_frame)
        ):
            # Create a modified copy of the type_df
            type_df_mod = type_df.copy()

            # Loop over rows using iterrows() of uploads_data_frames
            for index, row in self.uploads_data_frames.iterrows():
                value = row[column]
                existing_record = type_df[type_df[column] == value]

                # Check if the record already exists
                if existing_record.empty:
                    # Generate a new id if the record doesn't exist
                    new_id = type_df_mod['id'].max(
                    ) + 1 if not type_df_mod.empty else 1
                    new_record = pd.DataFrame(
                        {'id': [new_id], column: [value]})
                    # Append the new record to the modified data frame
                    type_df_mod = type_df_mod._append(
                        new_record, ignore_index=True)

            # Merge the uploads_data_frames with the modified type_df on the specified column
            merged_df = pd.merge(self.uploads_data_frames,
                                 type_df_mod, how='left')

            # Replace the original column with the new "id" column
            merged_df[column] = merged_df['id']
            merged_df = merged_df.drop('id', axis=1)

            # Update uploads_data_frames with the modified merged_df
            self.uploads_data_frames = merged_df.copy()

    def create_artificial_features(self):
        # Shortened name for self.uploads_data_frames
        uploads_df = self.uploads_data_frames

        # Calculate profit ratio for each movie
        uploads_df['profit_ratio'] = uploads_df['revenue'] / \
            uploads_df['budget']

        # Filter data based on quantiles for profit_ratio, revenue, and budget
        for col in ['profit_ratio', 'revenue', 'budget']:
            # Calculate quantile thresholds from the metadata DataFrame
            lower_threshold = self.meta_data_frame[col].min()
            upper_threshold = self.meta_data_frame[col].max()

            # Apply filtering to uploads_df
            uploads_df = uploads_df[
                (uploads_df[col] >= lower_threshold) &
                (uploads_df[col] <= upper_threshold)
            ]

        # Calculate additional features
        # Calculate the average profit ratio of a lead
        uploads_df['lead_average_profit_ratio'] = uploads_df.groupby(
            'lead')['profit_ratio'].transform('mean')
        # Calculate the average profit ratio of a director
        uploads_df['director_average_profit_ratio'] = uploads_df.groupby(
            'director')['profit_ratio'].transform('mean')
        # Calculate the count of times a lead has worked in a genre
        uploads_df['lead_worked_in_genre_count'] = uploads_df.groupby(
            ['lead', 'genre'])['title'].transform('count')
        # Calculate the count of times a director has worked in a genre
        uploads_df['director_worked_in_genre_count'] = uploads_df.groupby(
            ['director', 'genre'])['title'].transform('count')
        # Calculate the count of times a director has worked with a lead
        uploads_df['director_worked_with_lead_count'] = uploads_df.groupby(
            ['director', 'lead'])['title'].transform('count')

        # Drop rows with missing values (NaN)
        self.uploads_data_frames = uploads_df.dropna()

    def run_etl_process(self):
        self.download_processed_data()
        self.download_uploads()

        if (not isinstance(self.uploads_data_frames, pd.DataFrame)) or self.uploads_data_frames.empty:
            print("Info: No uploads to process")
            return

        self.filter_uploads()
        self.merge_in_type_definitions()
        self.create_artificial_features()

        # Concatenate the processed uploads with the existing meta_data_frame
        self.meta_data_frame = pd.concat(
            [self.meta_data_frame, self.uploads_data_frames], ignore_index=True).reset_index(drop=True)

        self.upload_processed_data_to_s3()
        self.clear_upload_data()


if __name__ == '__main__':
    etl_processor = ETLProcessor()
    etl_processor.run_etl_process()
