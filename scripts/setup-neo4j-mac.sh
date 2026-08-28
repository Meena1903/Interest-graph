#!/bin/bash
set -e

echo "=========================================="
echo "Neo4j Database Setup - macOS"
echo "=========================================="

echo "[1/2] Installing Neo4j via Homebrew..."
if ! command -v brew &> /dev/null; then
    echo "Homebrew is not installed. Installing Homebrew first..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

brew install neo4j

echo "[2/2] Starting Neo4j Service..."
brew services start neo4j

echo "=========================================="
echo "Setup Completed. Neo4j is running at http://localhost:7474"
echo "Credentials: neo4j / neo4j"
echo "=========================================="
