#!/bin/bash

# Fix .env leak in GitHub repository
# Run this script from the backend directory

echo "🔒 Fixing .env exposure in GitHub repository"
echo ""

# Check if we're in a git repo
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository"
    echo "   Please run this from: /Users/shreyasgpalimar/Downloads/Code Base/Toolset/backend"
    exit 1
fi

echo "Step 1: Removing .env from git tracking..."
git rm --cached .env

if [ $? -eq 0 ]; then
    echo "✅ .env removed from git tracking"
else
    echo "⚠️  .env might not be tracked or already removed"
fi

echo ""
echo "Step 2: Adding .gitignore..."
# .gitignore already created

echo "✅ .gitignore is in place"

echo ""
echo "Step 3: Committing the change..."
git add .gitignore
git commit -m "Remove .env from repository and add .gitignore"

echo ""
echo "Step 4: Pushing to GitHub..."
git push origin main

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DONE! .env is now removed from your repository"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  IMPORTANT: Change your secrets!"
echo ""
echo "Your old secrets are still visible in git history."
echo "Generate a new API key:"
echo ""
echo "  NEW_API_KEY=\$(openssl rand -hex 32)"
echo "  echo \$NEW_API_KEY"
echo ""
echo "Then update your .env file with the new API key."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
