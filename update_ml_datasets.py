import os
import pandas as pd
from functools import reduce
import boto3
from dotenv import load_dotenv

load_dotenv()

# AWS Credentials
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id,
                  aws_secret_access_key=aws_secret_access_key)

# Constants
CURRENT_DIR = os.path.dirname(__file__)

RAW_DIR = os.path.join(CURRENT_DIR, 'raw_datasets')
DATASETS_DIR = os.path.join(CURRENT_DIR, 'datasets')
UPLOADS_DIR = os.path.join(CURRENT_DIR, 'uploads')

UNIQUE_LEADS_FILE = 'unique_leads.csv'
UNIQUE_DIRECTORS_FILE = 'unique_directors.csv'
UNIQUE_GENRES_FILE = 'unique_genres.csv'
INPUT_DATA_FILE = 'input_data.csv'

UNIQUE_LEADS_PATH = os.path.join(DATASETS_DIR, UNIQUE_LEADS_FILE)
UNIQUE_DIRECTORS_PATH = os.path.join(DATASETS_DIR, UNIQUE_DIRECTORS_FILE)
UNIQUE_GENRES_PATH = os.path.join(DATASETS_DIR, UNIQUE_GENRES_FILE)
INPUT_DATA_PATH = os.path.join(DATASETS_DIR, INPUT_DATA_FILE)

PROCESSED_BUCKET = 'etl-project-data-processed'
UPLOADS_BUCKET = 'etl-project-uploads'


def download_files_from_s3(bucket_name, file_keys, local_directory):
    """
    Download files from an S3 bucket to a local directory.
    """
    os.makedirs(local_directory, exist_ok=True)

    for file_key in file_keys:
        local_file_path = os.path.join(local_directory, os.path.basename(file_key))
        s3.download_file(bucket_name, file_key, local_file_path)
        print(f"File downloaded to {local_file_path}")


def download_processed_data():
    bucket_name = PROCESSED_BUCKET
    file_keys = [INPUT_DATA_FILE, UNIQUE_DIRECTORS_FILE, UNIQUE_GENRES_FILE, UNIQUE_LEADS_FILE]
    local_directory = DATASETS_DIR
    download_files_from_s3(bucket_name, file_keys, local_directory)


def download_uploads():
    bucket_name = UPLOADS_BUCKET
    objects = s3.list_objects(Bucket=bucket_name)
    file_keys = [obj['Key'] for obj in objects.get('Contents', [])]
    local_directory = UPLOADS_DIR
    download_files_from_s3(bucket_name, file_keys, local_directory)


def upload_files_to_s3(bucket_name, local_files, local_directory):
    """
    Upload files from a local directory to an S3 bucket, overwriting existing files.
    """
    for local_file in local_files:
        local_file_path = os.path.join(local_directory, local_file)
        s3.upload_file(local_file_path, bucket_name, local_file)
        print(f"File uploaded to S3: {local_file}")


def upload_processed_data_to_s3():
    bucket_name = PROCESSED_BUCKET
    local_directory = DATASETS_DIR
    local_files = [file for file in os.listdir(local_directory) if file.endswith('.csv')]
    upload_files_to_s3(bucket_name, local_files, local_directory)


def clear_upload_data():
    objects = s3.list_objects(Bucket=UPLOADS_BUCKET)

    for obj in objects.get('Contents', []):
        file_key = obj['Key']
        s3.delete_object(Bucket=UPLOADS_BUCKET, Key=file_key)
        print(f"File deleted from S3: {file_key}")

    # Clear local files
    files = os.listdir(UPLOADS_DIR)

    for file in files:
        file_path = os.path.join(UPLOADS_DIR, file)
        os.remove(file_path)
        print(f"File deleted locally: {file_path}")


def import_uploads(directory_path):
    csv_files = [file for file in os.listdir(
        directory_path) if file.endswith('.csv')]
    data_frames = {}

    for csv_file in csv_files:
        file_path = os.path.join(directory_path, csv_file)
        data_frame_name = os.path.splitext(csv_file)[0]
        data_frames[data_frame_name] = pd.read_csv(file_path)

    return data_frames


def merge_two_data_frames(data_frame1, data_frame2):
    return pd.concat([data_frame1, data_frame2], ignore_index=True).drop_duplicates(subset='title').reset_index(drop=True)


def filter_data_frame(input_data_frame, uploads_data_frames):
    expected_columns = ['title', 'lead',
                        'director', 'genre', 'revenue', 'budget']

    uploads_data_frames = [data_frame.dropna(subset=expected_columns) for data_frame in uploads_data_frames.values() if all(
        col in data_frame.columns for col in expected_columns) and len(data_frame.columns) == len(expected_columns)]

    uploads_data_frames = reduce(merge_two_data_frames, uploads_data_frames)

    max_budget, min_budget = input_data_frame['budget'].max(
    ), input_data_frame['budget'].min()
    max_revenue, min_revenue = input_data_frame['revenue'].max(
    ), input_data_frame['revenue'].min()

    uploads_data_frames = uploads_data_frames[
        (uploads_data_frames['budget'] < max_budget) &
        (uploads_data_frames['budget'] > min_budget) &
        (uploads_data_frames['revenue'] < max_revenue) &
        (uploads_data_frames['revenue'] > min_revenue)
    ].drop_duplicates(subset='title').reset_index(drop=True)

    uploads_data_frames = uploads_data_frames[
        ~uploads_data_frames['title'].isin(input_data_frame['title'])
    ]

    return uploads_data_frames


def update_type_definition(data_frame, column, row):
    value = row[column]
    existing_record = data_frame[data_frame[column] == value]

    if existing_record.empty:
        new_id = data_frame['id'].max() + 1 if not data_frame.empty else 1
        new_record = pd.DataFrame({'id': [new_id], column: [value]})
        data_frame = data_frame._append(new_record, ignore_index=True)
        _id = new_id
    else:
        _id = existing_record['id'].iloc[0]

    return data_frame, _id


def process_type_definitions(type_definition_tuples, valid_data_frame):
    for column, file_path in type_definition_tuples:
        data_frame = pd.read_csv(file_path)

        # Loop over rows using iterrows()
        for index, row in valid_data_frame.iterrows():
            data_frame, _id = update_type_definition(data_frame, column, row)

        data_frame.to_csv(file_path, index=False)

        # Merge the two DataFrames on the specified column
        merged_data_frame = pd.merge(valid_data_frame, data_frame, how='left')

        # Replace the original column with the new "id" column
        merged_data_frame[column] = merged_data_frame['id']
        merged_data_frame = merged_data_frame.drop('id', axis=1)

        # Update valid_data_frame with the modified merged_data_frame
        valid_data_frame = merged_data_frame.copy()

    return valid_data_frame


def create_artificial_features(data):
    # Calculate profit ratio for each movie
    data['profit_ratio'] = data['revenue'] / data['budget']

    # Filter based on quantiles for profit_ratio, revenue, and budget
    for col in ['profit_ratio', 'revenue', 'budget']:
        lower_threshold = input_data_frame[col].min()
        upper_threshold = input_data_frame[col].max()
        data = data[(data[col] >= lower_threshold) &
                    (data[col] <= upper_threshold)]

    # Calculate the average profit ratio of a lead
    data['lead_average_profit_ratio'] = data.groupby(
        'lead')['profit_ratio'].transform('mean')
    # Calculate the average profit ratio of a director
    data['director_average_profit_ratio'] = data.groupby(
        'director')['profit_ratio'].transform('mean')
    # Calculate if lead has worked in genre and count occurrences
    data['lead_worked_in_genre_count'] = data.groupby(
        ['lead', 'genre'])['title'].transform('count')
    # Calculate if director has worked in genre and count occurrences
    data['director_worked_in_genre_count'] = data.groupby(
        ['director', 'genre'])['title'].transform('count')
    # Calculate if director has worked with lead
    data['director_worked_with_lead_count'] = data.groupby(
        ['director', 'lead'])['title'].transform('count')

    return data.dropna()


# Call the functions
print("Download Processed Data")
download_processed_data()
print("Download Uploads")
download_uploads()

input_data_frame = pd.read_csv(INPUT_DATA_PATH)

type_definition_tuples = [
    ('director', UNIQUE_DIRECTORS_PATH),
    ('genre', UNIQUE_GENRES_PATH),
    ('lead', UNIQUE_LEADS_PATH),
]

uploads_data_frames = import_uploads(UPLOADS_DIR)

if (not uploads_data_frames):
    print("No Uploads To Handle")
else:
    valid_data_frame = filter_data_frame(input_data_frame, uploads_data_frames)

    type_defined_data_frame = process_type_definitions(type_definition_tuples, valid_data_frame)

    augmented_data_frame = create_artificial_features(type_defined_data_frame)

    input_data_frame = pd.concat([input_data_frame, augmented_data_frame], ignore_index=True).reset_index(drop=True)
    input_data_frame.to_csv(INPUT_DATA_PATH, index=False)

    print("Upload Processed Data To S3")
    upload_processed_data_to_s3()
    print("Clear Upload Data")
    clear_upload_data()    
