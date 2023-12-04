# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Add an interactive shell
RUN sudo /bin/bash

# Install any needed packages specified in requirements.txt
RUN sudo pip install -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Run the Flask application
CMD ["flask", "run"]
