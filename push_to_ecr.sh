#!/bin/bash

# Source the Python script to get the values
source ./env.py

# AWS Configuration
AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
echo "$AWS_ACCESS_KEY_ID"
# Set your AWS configuration
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="690469543125"
ECR_REPOSITORY="etl-project-container-repository"

# Build the Docker image
echo "Building the Docker image..."
podman build -t aws_etl_project_image -f ./Dockerfile .

# Authenticate with ECR
echo "Authenticating with ECR..."
aws ecr get-login-password --region $AWS_REGION | podman login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag your local Podman image with the ECR repository URI
echo "Tagging the local image..."
podman tag aws_etl_project_image:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest

# Push the image to ECR using the AWS access key and secret key
echo "Pushing the image to ECR..."
podman push --creds=$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest

echo "Image successfully pushed to ECR."