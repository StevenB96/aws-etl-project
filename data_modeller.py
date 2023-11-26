import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import os

# Constants
CURRENT_DIR = os.path.dirname(__file__)

DATASETS_DIR = os.path.join(CURRENT_DIR, 'datasets')
MODEL_DIR = os.path.join(CURRENT_DIR, 'ml_model')

INPUT_DATA_FILE_PATH = os.path.join(DATASETS_DIR, 'input_data.csv')
MODEL_FILE_PATH = os.path.join(MODEL_DIR, 'decision_tree_model.pkl')

# Load the input_data from the CSV file
input_data = pd.read_csv(INPUT_DATA_FILE_PATH)

# List of ml features
ml_features = [
    'budget',
    'director_average_profit_ratio',
    'lead_average_profit_ratio',
    'lead_worked_in_genre_count',
    'director_worked_in_genre_count',
    'director_worked_with_lead_count',
]

# Data preparation
X = input_data[ml_features]
T = input_data[['profit_ratio']]
X_train, X_test, y_profit_ratio_train, y_profit_ratio_test = train_test_split(
    X,
    T,
    test_size=0.2,
    random_state=42
)

# Model training
profit_ratio_model = DecisionTreeRegressor()
profit_ratio_model.fit(X_train, y_profit_ratio_train)

# Model evaluation
profit_ratio_predictions = profit_ratio_model.predict(X_test)
profit_ratio_mse = mean_squared_error(
    y_profit_ratio_test, profit_ratio_predictions)
profit_ratio_r2 = r2_score(
    y_profit_ratio_test, profit_ratio_predictions)
feature_importances = profit_ratio_model.feature_importances_

# Print the best result
print('\nBest Result:')
print(f'Profit Ratio MSE: {profit_ratio_mse}')
print(f'Profit Ratio R-squared: {profit_ratio_r2}')

feature_importance_df = pd.DataFrame(
    {'Feature': ml_features, 'Importance': feature_importances})
feature_importance_df = feature_importance_df.sort_values(
    by='Importance', ascending=False)

print(feature_importance_df)

# Save the profit_ratio model to a file
joblib.dump(profit_ratio_model, MODEL_FILE_PATH)
