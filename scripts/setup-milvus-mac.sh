#!/bin/bash
set -e

echo "=========================================="
echo "Milvus Standalone Setup (Docker) - macOS"
echo "=========================================="

echo "[1/2] Checking if Docker is installed..."
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker Desktop for Mac first: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

echo "[2/2] Downloading Milvus Standalone Compose configurations..."
curl -L https://github.com/milvus-io/milvus/releases/download/v2.4.0/milvus-standalone-docker-compose.yml -o docker-compose.yml

echo "Starting Milvus..."
docker-compose up -d

echo "=========================================="
echo "Setup Completed. Milvus Standalone is running."
echo "Ports: 19530 (gRPC), 9091 (REST API)"
echo "=========================================="
