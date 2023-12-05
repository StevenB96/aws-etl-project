#!/bin/bash

# Source the Python script to get the values
source ./env.py

# Check if required variables are set
if [[ -z "$AWS_ACCESS_KEY_ID" || -z "$AWS_SECRET_ACCESS_KEY" ]]; then
    echo "Error: AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY not set in env.py"
    exit 1
fi

# AWS Configuration
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="690469543125"
ECR_REPOSITORY="etl-project-container-repository"

# Build the Docker image
echo "Building the Docker image..."
podman build -t aws_etl_project_image -f ./Dockerfile .

# Check if the build was successful
if [[ $? -ne 0 ]]; then
    echo "Error: Docker image build failed"
    exit 1
fi

# Authenticate with ECR
echo "Authenticating with ECR..."
aws ecr get-login-password --region $AWS_REGION | podman login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Check if authentication was successful
if [[ $? -ne 0 ]]; then
    echo "Error: Authentication with ECR failed"
    exit 1
fi

# Tag your local Podman image with the ECR repository URI
echo "Tagging the local image..."
podman tag aws_etl_project_image:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest

# Push the image to ECR using the AWS access key and secret key
echo "Pushing the image to ECR..."
podman push --creds=$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest

# Check if the push was successful
if [[ $? -ne 0 ]]; then
    echo "Error: Image push to ECR failed"
    exit 1
fi

echo "Image successfully pushed to ECR."
