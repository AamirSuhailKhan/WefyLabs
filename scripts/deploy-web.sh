#!/bin/bash
set -e

echo "🚀 Deploying LeadScore Web App to Vercel..."

# Check if vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI is not installed. Install via: npm i -g vercel"
    exit 1
fi

cd apps/web
echo "📦 Building and deploying production frontend..."
vercel --prod

echo "✅ LeadScore Web App successfully deployed to Vercel!"
