import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import boto3
from io import BytesIO
from env import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY


class MLModelTrainer:
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
        # Constants
        # S3 buckets and file names
        self.DATASETS_BUCKET = 'etl-project-data-processed'
        self.MODEL_BUCKET = 'etl-project-ml-model'
        self.INPUT_DATA_FILE = 'input_data.csv'
        self.MODEL_FILE = 'decision_tree_model.pkl'
        # List of ml features
        self.ml_features = [
            'budget',
            'director_average_profit_ratio',
            'lead_average_profit_ratio',
            'lead_worked_in_genre_count',
            'director_worked_in_genre_count',
            'director_worked_with_lead_count',
        ]

    def load_data_from_s3(self):
        # Download and read CSV content from S3 for input data
        file_content = self.s3.get_object(
            Bucket=self.DATASETS_BUCKET, Key=self.INPUT_DATA_FILE)['Body'].read()
        self.meta_data_frame = pd.read_csv(BytesIO(file_content))
        print(f"Dataframe created from s3: {self.INPUT_DATA_FILE}")

    def prepare_data(self):
        # Data preparation
        X = self.meta_data_frame[self.ml_features]
        T = self.meta_data_frame[['profit_ratio']]
        self.X_train, self.X_test, self.y_profit_ratio_train, self.y_profit_ratio_test = train_test_split(
            X,
            T,
            test_size=0.2,
            random_state=42
        )

    def train_model(self):
        # Model training
        self.profit_ratio_model = DecisionTreeRegressor()
        self.profit_ratio_model.fit(self.X_train, self.y_profit_ratio_train)

    def evaluate_model(self):
        # Model evaluation
        profit_ratio_predictions = self.profit_ratio_model.predict(self.X_test)
        self.profit_ratio_mse = mean_squared_error(
            self.y_profit_ratio_test, profit_ratio_predictions)
        self.profit_ratio_r2 = r2_score(
            self.y_profit_ratio_test, profit_ratio_predictions)
        self.feature_importances = self.profit_ratio_model.feature_importances_

        # Print the training result
        print(f'Profit Ratio MSE: {self.profit_ratio_mse}')
        print(f'Profit Ratio R-squared: {self.profit_ratio_r2}')

        feature_importance_df = pd.DataFrame(
            {'Feature': self.ml_features, 'Importance': self.feature_importances})
        feature_importance_df = feature_importance_df.sort_values(
            by='Importance', ascending=False)

        print(feature_importance_df)

    def save_model_to_s3(self):
        # Save the profit_ratio model to a file-like object
        model_file_object = BytesIO()
        joblib.dump(self.profit_ratio_model, model_file_object)

        # Upload the model file to S3
        self.s3.put_object(Body=model_file_object.getvalue(),
                           Bucket=self.MODEL_BUCKET, Key=self.MODEL_FILE)
        print(f"Model uploaded to S3: {self.MODEL_FILE}")

    def run_training_process(self):
        self.load_data_from_s3()
        self.prepare_data()
        self.train_model()
        self.evaluate_model()
        self.save_model_to_s3()


if __name__ == '__main__':
    ml_model_trainer = MLModelTrainer()
    ml_model_trainer.run_training_process()
