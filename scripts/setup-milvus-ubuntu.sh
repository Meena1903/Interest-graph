#!/bin/bash
set -e

echo "=========================================="
echo "Milvus Standalone Setup (Docker) - Ubuntu"
echo "=========================================="

echo "[1/2] Installing Docker & Compose if not present..."
if ! command -v docker &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose
fi

echo "[2/2] Downloading Milvus Docker-Compose manifest..."
wget https://github.com/milvus-io/milvus/releases/download/v2.4.0/milvus-standalone-docker-compose.yml -O docker-compose.yml

echo "Starting Milvus containers..."
sudo docker-compose up -d

echo "=========================================="
echo "Setup Completed. Milvus Standalone is running."
echo "Ports: 19530 (gRPC), 9091 (REST API)"
echo "=========================================="
