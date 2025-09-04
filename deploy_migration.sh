#!/bin/bash

# Deploy script for cor_calendario migration
# Usage: ./deploy_migration.sh

echo "🚀 Starting migration deployment..."

# Replace with your actual Render database connection string
DATABASE_URL="postgresql://username:password@hostname:port/database_name"

echo "📊 Running migration on production database..."

# Execute migration
psql "$DATABASE_URL" -f migration_cor_calendario.sql

if [ $? -eq 0 ]; then
    echo "✅ Migration completed successfully!"
    echo "📦 You can now deploy your application code to Render"
    echo ""
    echo "🔍 Verification commands:"
    echo "SELECT cor_calendario FROM vendedores LIMIT 5;"
    echo ""
else
    echo "❌ Migration failed! Check the errors above"
    exit 1
fi

echo "🎯 Next steps:"
echo "1. Commit and push your code changes"  
echo "2. Render will automatically deploy the updated application"
echo "3. Test the color picker in vendor management"