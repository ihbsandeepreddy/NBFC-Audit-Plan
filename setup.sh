#!/bin/bash
echo "Setting up NBFC Audit Intelligence Platform..."

# Copy env
[ ! -f .env ] && cp .env.example .env && echo ".env created from example"

# Build and start containers
docker-compose up -d --build

echo "Waiting for services to be healthy..."
sleep 10

echo ""
echo "Platform is running at:"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "Default login: admin@nbfc.local / admin123"
