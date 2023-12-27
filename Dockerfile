# Use a smaller base image
FROM python:3.11-alpine

# Install system dependencies
RUN apk --no-cache add sudo net-tools lsof htop strace tcpdump iproute2 curl vim gfortran \
    && rm -rf /var/cache/apk/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Create a virtual environment and install dependencies
RUN python -m venv venv \
    && source venv/bin/activate \
    && pip install --no-cache-dir -r requirements.txt \
    && deactivate

# Install Gunicorn
RUN pip install gunicorn

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Use Gunicorn to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:80", "--timeout", "300", "--log-level", "debug", "app:app"]
