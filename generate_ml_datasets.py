import os
import pandas as pd
import warnings

# Constants
CURRENT_DIR = os.path.dirname(__file__)

RAW_DIR = os.path.join(CURRENT_DIR, 'raw_datasets')
PROCESSED_DIR = os.path.join(CURRENT_DIR, 'datasets')

CREDITS_FILE = os.path.join(RAW_DIR, 'credits.csv')
MOVIES_METADATA_FILE = os.path.join(RAW_DIR, 'movies_metadata.csv')

UNIQUE_LEADS_FILE = 'unique_leads.csv'
UNIQUE_DIRECTORS_FILE = 'unique_directors.csv'
UNIQUE_GENRES_FILE = 'unique_genres.csv'
INPUT_DATA_FILE = 'input_data.csv'

CREDITS_DATA_FRAME_COLUMNS = [
    'id',
    'cast',
    'crew'
]

MOVIES_METADATA_DATA_FRAME_COLUMNS = [
    'id',
    'title',
    'genres',
    'budget',
    'revenue'
]

ML_INPUT_DATA_FRAME_COLUMNS = [
    'title',
    'lead',
    'director',
    'genre',
    'revenue',
    'budget',
    'profit_ratio',
    'director_average_profit_ratio',
    'lead_average_profit_ratio',
    'lead_worked_in_genre_count',
    'director_worked_in_genre_count',
    'director_worked_with_lead_count',
]


def save_unique_data(data, column_name, output_filename):
    # Get unique values from the data
    unique_values = data[column_name].unique()

    # Create a DataFrame with unique values and an "id" column
    unique_values_df = pd.DataFrame(
        {'id': range(1, len(unique_values) + 1), column_name: unique_values})

    # Save to a CSV file
    unique_values_df.to_csv(os.path.join(
        PROCESSED_DIR, output_filename), index=False)

    # Create a mapping dictionary for the original values to their corresponding IDs
    mapping = unique_values_df.set_index(column_name)['id'].to_dict()

    # Replace the original column with the 'id' column
    data[column_name] = data[column_name].map(mapping)


def save_data(combined_data):
    # Save unique leads, directors, and genres
    save_unique_data(combined_data, 'lead', UNIQUE_LEADS_FILE)
    save_unique_data(combined_data, 'director', UNIQUE_DIRECTORS_FILE)
    save_unique_data(combined_data, 'genre', UNIQUE_GENRES_FILE)

    # Save the combined data to a CSV file using Pandas to_csv
    combined_data.to_csv(os.path.join(
        PROCESSED_DIR, INPUT_DATA_FILE), index=False)


def clean_data(data):
    # Convert 'id' columns to numeric and handle errors
    data['id'] = pd.to_numeric(data['id'], errors='coerce')
    data = data.dropna(subset=['id'])
    data['id'] = data['id'].astype('Int64')

    # Convert 'revenue' and 'budget' columns to numeric and handle errors
    for col in ['revenue', 'budget']:
        data[col] = pd.to_numeric(data[col], errors='coerce')
        data = data.dropna(subset=[col])
        data[col] = data[col].astype(float)

    # Filter English language and released movies
    data = data[data['original_language'] == 'en']
    data = data[data['status'] == 'Released']

    # Filter movies based on budget, revenue, and vote count criteria
    data = data[(data['revenue'] > 0) & (data['budget'] > 0)]

    return data


def create_artificial_features(data):
    # Calculate profit ratio for each movie
    data['profit_ratio'] = data['revenue'] / data['budget']

    # Filter based on quantiles for profit_ratio, revenue, and budget
    for col in ['profit_ratio', 'revenue', 'budget']:
        upper_threshold = data[col].quantile(0.95)
        lower_threshold = data[col].quantile(0.05)
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


def main():
    # Load Set A (credits) from a CSV file
    credits_data_frame = pd.read_csv(CREDITS_FILE)

    # Load Set B (metadata) from a CSV file
    movies_metadata_data_frame = pd.read_csv(MOVIES_METADATA_FILE)

    # Clean data for Set B
    movies_metadata_data_frame = clean_data(movies_metadata_data_frame)

    # Select and rename the columns you want to keep in Set A
    credits_data_frame = credits_data_frame[CREDITS_DATA_FRAME_COLUMNS]

    credits_data_frame = credits_data_frame.dropna(subset=['cast', 'crew'])
    credits_data_frame['cast'] = credits_data_frame['cast'].apply(eval)
    credits_data_frame['lead'] = credits_data_frame['cast'].apply(
        lambda x: x[0]['name'] if x else None)
    credits_data_frame['crew'] = credits_data_frame['crew'].apply(eval)
    credits_data_frame['director'] = credits_data_frame['crew'].apply(lambda x: next(
        (member['name'] for member in x if member['job'] == 'Director'), None))

    # Select and rename the columns you want to keep in Set B
    movies_metadata_data_frame = movies_metadata_data_frame[MOVIES_METADATA_DATA_FRAME_COLUMNS]

    movies_metadata_data_frame = movies_metadata_data_frame.dropna(subset=[
                                                                   'genres'])
    movies_metadata_data_frame['genres'] = movies_metadata_data_frame['genres'].apply(
        eval)
    movies_metadata_data_frame['genre'] = movies_metadata_data_frame['genres'].apply(
        lambda x: x[0]['name'] if x else None)
    movies_metadata_data_frame = movies_metadata_data_frame.drop([
                                                                 'genres'], axis=1)

    # Merge Set A and Set B based on the 'id' column using Pandas merge
    combined_data = credits_data_frame.merge(
        movies_metadata_data_frame, on='id', how='inner')

    # Create artificial features
    combined_data = create_artificial_features(combined_data)

    # Select and rename the columns you want to keep in Set A
    combined_data = combined_data[ML_INPUT_DATA_FRAME_COLUMNS]

    # Save data
    save_data(combined_data)


if __name__ == '__main__':
    warnings.filterwarnings("ignore")
    main()
