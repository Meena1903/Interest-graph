@echo off
echo ==========================================
echo Milvus Standalone Setup (Docker) - Windows
echo ==========================================

echo [1/2] Downloading Docker Compose configuration file for Milvus standalone...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/milvus-io/milvus/releases/download/v2.4.0/milvus-standalone-docker-compose.yml' -OutFile 'docker-compose.yml'"

echo [2/2] Launching Milvus via Docker Compose...
docker-compose up -d

echo ==========================================
echo Setup Completed. Milvus is running.
echo Ports: 19530 (gRPC), 9091 (REST API)
echo ==========================================
