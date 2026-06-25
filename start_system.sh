#!/bin/bash
# Start the complete system: Local Model Server + Backend API

echo "========================================="
echo "Starting Decathlon Smart Shopping System"
echo "========================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found"
    exit 1
fi

echo "Architecture:"
echo "  User → api_swagger.py (port 5000)"
echo "        ↓"
echo "  local_model_server.py (port 8000)"
echo "        ↓"
echo "  Qwen3-4B + LoRA → Tools → PostgreSQL"
echo ""
echo "This will start:"
echo "  1. Local Model Server (Qwen3-4B on port 8000)"
echo "  2. Backend API (port 5000)"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

# Activate MLX venv if it exists
if [ -d "training/venv_mlx" ]; then
    echo "Activating MLX virtual environment..."
    source training/venv_mlx/bin/activate
fi

# Check if MLX is installed
python3 -c "import mlx_lm" 2>/dev/null || {
    echo "❌ mlx_lm not installed"
    echo "   Install with: cd training && ./setup_mlx.sh"
    exit 1
}

# Start local model server in background
echo ""
echo "========================================="
echo "Step 1: Starting Local Model Server"
echo "========================================="

cd training
python3 local_model_server.py &
MODEL_PID=$!
cd ..

echo "✓ Model server starting (PID: $MODEL_PID)"
echo "   Waiting 10 seconds for model to load..."
sleep 10

# Check if model server is running
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ Model server is healthy"
else
    echo "⚠️  Model server not responding yet (still loading)"
    echo "   Will continue anyway..."
fi

# Start backend API
echo ""
echo "========================================="
echo "Step 2: Starting Backend API"
echo "========================================="

cd backend
python3 api_swagger.py &
API_PID=$!
cd ..

echo "✓ Backend API starting (PID: $API_PID)"
echo "   Waiting 5 seconds for API to initialize..."
sleep 5

# Check if API is running
if curl -s http://localhost:5000/api/v1/system/health > /dev/null; then
    echo "✓ Backend API is healthy"
else
    echo "❌ Backend API failed to start"
    kill $MODEL_PID 2>/dev/null
    kill $API_PID 2>/dev/null
    exit 1
fi

echo ""
echo "========================================="
echo "✅ SYSTEM READY"
echo "========================================="
echo ""
echo "API Endpoints:"
echo "  POST http://localhost:5000/api/v1/query"
echo "  GET  http://localhost:5000/api/v1/system/health"
echo "  GET  http://localhost:5000/docs (Swagger)"
echo ""
echo "Model Server:"
echo "  GET  http://localhost:8000/health"
echo ""
echo "Test command:"
echo "  curl -X POST http://localhost:5000/api/v1/query \\"
echo "       -H 'Api-Key: decathlon_smart_search_2024_secure_key_abc123xyz' \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"query\":\"running shoes under 5000\"}'"
echo ""
echo "Press Ctrl+C to stop..."
echo ""

# Wait for Ctrl+C
trap "echo ''; echo 'Stopping system...'; kill $MODEL_PID 2>/dev/null; kill $API_PID 2>/dev/null; echo 'System stopped'; exit 0" INT

# Keep script running
wait
