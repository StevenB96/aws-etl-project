import os
import sys

# Get the directory of the current script
current_dir = os.path.dirname(__file__)

# Add the current directory and the virtual environment to the Python path
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, 'venv', 'lib', 'python3.11', 'site-packages'))  # Adjust the path and Python version as needed

# Import and run the Flask application
from app import app as application
