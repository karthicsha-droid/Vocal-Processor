# Script to push vocal-mixer to GitHub
# Run this after restarting PowerShell

cd C:\Users\Public\vocal-mixer

# Initialize git repository
git init

# Add remote
git remote add origin https://github.com/karthicsha-droid/Vocal-Processor.git

# Add all files
git add .

# Commit
git commit -m "Initial commit: Real-time vocal processor with auto-detection"

# Rename branch to main
git branch -M main

# Push to GitHub
git push -u origin main

Write-Host "`nSuccessfully pushed to GitHub!" -ForegroundColor Green
