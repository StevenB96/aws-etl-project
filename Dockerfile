# Use a smaller base image
FROM python:3.11-alpine

# Set the working directory in the container
WORKDIR /app

# Copy only the requirements file, and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install Gunicorn
RUN pip install gunicorn

# Copy the rest of the application
COPY . /app/

# Remove unnecessary packages and clean up
RUN apk del .build-deps \
    && rm -rf /var/cache/apk/*

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Use Gunicorn to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:80", "--timeout", "300", "--log-level", "debug", "app:app"]
