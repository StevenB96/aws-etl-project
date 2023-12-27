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

# Build the container image using the specified service
echo "Building the container image using $CONTAINER_SERVICE..."
$CONTAINER_SERVICE build -t aws_etl_project_image -f ./Dockerfile .

# Check if the build was successful
if [[ $? -ne 0 ]]; then
    echo "Error: Container image build failed"
    exit 1
fi

# Set AWS credentials in the environment
export "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"
export "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY"

# Authenticate with ECR
echo "Authenticating with ECR..."
aws ecr get-login-password --region $AWS_REGION | $CONTAINER_SERVICE login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Check if authentication was successful
if [[ $? -ne 0 ]]; then
    echo "Error: Authentication with ECR failed"
    exit 1
fi

# Set image uri
export ECR_IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest"

# Tag your local container image with the ECR repository URI
echo "Tagging the local image..."
$CONTAINER_SERVICE tag aws_etl_project_image:latest "$ECR_IMAGE_URI"

# Push the image to ECR
echo "Pushing the image to ECR..."
$CONTAINER_SERVICE push "$ECR_IMAGE_URI"

# Check if the push was successful
if [[ $? -ne 0 ]]; then
    echo "Error: Image push to ECR failed"
    exit 1
fi

# Create imagedefinitions.json using variables
printf '[{"name":"%s","imageUri":"%s"}]' "$ECS_CONTAINER_NAME" "$ECR_IMAGE_URI" > imagedefinitions.json

# Delete the local container image
echo "Deleting the local container image..."
$CONTAINER_SERVICE rmi aws_etl_project_image:latest

# Pruning unused images
echo "Pruning unused images..."
podman system prune --all --force


echo "Image successfully pushed to ECR."
