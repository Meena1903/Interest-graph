#!/bin/bash
set -e

echo "=========================================="
echo "Neo4j Database Setup - Ubuntu/Debian"
echo "=========================================="

echo "[1/3] Installing Java Runtime dependency..."
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk

echo "[2/3] Adding Neo4j package repositories..."
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/neo4j.gpg
echo "deb [signed-by=/usr/share/keyrings/neo4j.gpg] https://debian.neo4j.com stable latest" | sudo tee -a /etc/apt/sources.list.d/neo4j.list

echo "[3/3] Installing and starting Neo4j..."
sudo apt-get update
sudo apt-get install -y neo4j
sudo systemctl enable neo4j
sudo systemctl start neo4j

echo "=========================================="
echo "Setup Completed. Neo4j is running at http://localhost:7474"
echo "Credentials: neo4j / neo4j"
echo "=========================================="
