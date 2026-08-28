@echo off
echo ==========================================
echo Neo4j Database Setup - Windows
echo ==========================================

echo [1/3] Downloading Neo4j Community Edition zip...
powershell -Command "Invoke-WebRequest -Uri 'https://neo4j.com/artifact.php?name=neo4j-community-5.20.0-windows.zip' -OutFile 'neo4j-community.zip'"

echo [2/3] Extracting Neo4j...
powershell -Command "Expand-Archive -Path 'neo4j-community.zip' -DestinationPath 'neo4j-server' -Force"

echo [3/3] Launching Neo4j Service...
cd neo4j-server\neo4j-community-5.20.0\bin
neo4j.bat install-service
neo4j.bat start

echo ==========================================
echo Setup Completed. Neo4j is running at http://localhost:7474
echo Credentials: neo4j / neo4j (change on first login)
echo ==========================================
