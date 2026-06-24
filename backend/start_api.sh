#!/bin/bash
# Quick start script for the new Agent API

echo "========================================="
echo "Starting Agent API"
echo "========================================="

# Check if we're in the backend directory
if [ ! -f "api/agent.py" ]; then
    echo "❌ Error: Must run from backend/ directory"
    echo "   cd backend && ./start_api.sh"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found"
    exit 1
fi

echo "✓ Python: $(python3 --version)"

# Check dependencies
echo ""
echo "Checking dependencies..."
python3 -c "import flask" 2>/dev/null || {
    echo "❌ Flask not installed"
    echo "   Install with: pip install -r requirements_render.txt"
    exit 1
}

python3 -c "import pydantic" 2>/dev/null || {
    echo "❌ Pydantic not installed"
    echo "   Install with: pip install -r requirements_render.txt"
    exit 1
}

python3 -c "import psycopg2" 2>/dev/null || {
    echo "❌ psycopg2 not installed"
    echo "   Install with: pip install -r requirements_render.txt"
    exit 1
}

echo "✓ Dependencies installed"

# Check environment variables
echo ""
echo "Checking environment variables..."

if [ -z "$POSTGRES_HOST" ]; then
    echo "⚠️  POSTGRES_HOST not set, using default: localhost"
    export POSTGRES_HOST=localhost
fi

if [ -z "$POSTGRES_PORT" ]; then
    echo "⚠️  POSTGRES_PORT not set, using default: 5432"
    export POSTGRES_PORT=5432
fi

if [ -z "$POSTGRES_DB" ]; then
    echo "⚠️  POSTGRES_DB not set, using default: decathlon_rag"
    export POSTGRES_DB=decathlon_rag
fi

if [ -z "$POSTGRES_USER" ]; then
    echo "⚠️  POSTGRES_USER not set, using default: postgres"
    export POSTGRES_USER=postgres
fi

if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "⚠️  Warning: POSTGRES_PASSWORD not set"
    echo "   Set with: export POSTGRES_PASSWORD=your_password"
fi

if [ -z "$API_KEY" ]; then
    echo "⚠️  API_KEY not set, using default: decathlon_agent_api_key_2024"
    export API_KEY=decathlon_agent_api_key_2024
fi

echo "✓ Environment configured"
echo "   POSTGRES_HOST: $POSTGRES_HOST"
echo "   POSTGRES_PORT: $POSTGRES_PORT"
echo "   POSTGRES_DB: $POSTGRES_DB"
echo "   POSTGRES_USER: $POSTGRES_USER"
echo "   API_KEY: ${API_KEY:0:10}..."

# Check database connection
echo ""
echo "Testing database connection..."
python3 << 'EOF'
import sys
try:
    import psycopg2
    import os
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        database=os.getenv('POSTGRES_DB', 'decathlon_rag'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    conn.close()
    print("✓ Database connection successful")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "Fix database connection issues before starting the API"
    exit 1
fi

# Start the API
echo ""
echo "========================================="
echo "Starting API on port 5000..."
echo "========================================="
echo ""
echo "Endpoints:"
echo "  Health:  http://localhost:5000/health"
echo "  Docs:    http://localhost:5000/docs"
echo "  API:     http://localhost:5000/api/v1/agent"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 api/agent.py
