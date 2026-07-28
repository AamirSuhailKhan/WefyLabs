#!/bin/bash
set -e

echo "🚀 Deploying LeadScore API to Railway..."

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI is not installed. Install via: npm i -g @railway/cli"
    exit 1
fi

cd apps/api
echo "📦 Building and pushing deployment package..."
railway up --detach

echo "✅ LeadScore API successfully deployed to Railway!"
