#!/bin/bash

# Default container service
CONTAINER_SERVICE="podman"

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    key="$1"

    case $key in
        --container-service)
            CONTAINER_SERVICE="$2"
            shift
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

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
ECS_CONTAINER_NAME="etl-project-container"
ECR_REPOSITORY="etl-project-container-repository"

# Authenticate with ECR
echo "Authenticating with ECR..."
AWS_ECR_PASSWORD=$(aws ecr get-login-password --region $AWS_REGION)
$CONTAINER_SERVICE login --username AWS --password $AWS_ECR_PASSWORD $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Check if authentication was successful
if [[ $? -ne 0 ]]; then
    echo "Error: Authentication with ECR failed"
    exit 1
fi

# Pull the ECR image
echo "Pulling the ECR image..."
$CONTAINER_SERVICE pull $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest

# Check if the pull was successful
if [[ $? -ne 0 ]]; then
    echo "Error: Image pull from ECR failed"
    exit 1
fi

# Run the ECR image
echo "Running the ECR image..."
$CONTAINER_SERVICE run -d --name $ECS_CONTAINER_NAME $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest

# Check if the container is running
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to run the container"
    exit 1
fi

echo "Container successfully started from ECR image."
