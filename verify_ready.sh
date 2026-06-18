#!/bin/bash
# Verify everything is ready for deployment

echo "========================================="
echo "DEPLOYMENT READINESS CHECK"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Check 1: Adapter files
echo "1. Checking LoRA adapter..."
if [ -f "training/outputs/qwen25_1_5b_lora_hf/adapter_model.safetensors" ] && \
   [ -f "training/outputs/qwen25_1_5b_lora_hf/adapter_config.json" ] && \
   [ -f "training/outputs/qwen25_1_5b_lora_hf/tokenizer.json" ]; then
    echo -e "   ${GREEN}✓${NC} LoRA adapter files present"
else
    echo -e "   ${RED}✗${NC} LoRA adapter files missing"
    ERRORS=$((ERRORS + 1))
fi

# Check 2: Dependencies files
echo ""
echo "2. Checking dependency files..."
if [ -f "requirements_local_server.txt" ]; then
    echo -e "   ${GREEN}✓${NC} requirements_local_server.txt exists"
else
    echo -e "   ${RED}✗${NC} requirements_local_server.txt missing"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "backend/requirements_render.txt" ]; then
    echo -e "   ${GREEN}✓${NC} backend/requirements_render.txt exists"
else
    echo -e "   ${RED}✗${NC} backend/requirements_render.txt missing"
    ERRORS=$((ERRORS + 1))
fi

# Check 3: Server files
echo ""
echo "3. Checking server files..."
if [ -f "local_model_server.py" ]; then
    echo -e "   ${GREEN}✓${NC} local_model_server.py exists"
else
    echo -e "   ${RED}✗${NC} local_model_server.py missing"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "backend/local_model_client.py" ]; then
    echo -e "   ${GREEN}✓${NC} backend/local_model_client.py exists"
else
    echo -e "   ${RED}✗${NC} backend/local_model_client.py missing"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "test_local_model.py" ]; then
    echo -e "   ${GREEN}✓${NC} test_local_model.py exists"
else
    echo -e "   ${RED}✗${NC} test_local_model.py missing"
    ERRORS=$((ERRORS + 1))
fi

# Check 4: Backend files updated
echo ""
echo "4. Checking backend integration..."
if grep -q "from local_model_client import" backend/hf_planner.py 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} backend/hf_planner.py uses local_model_client"
else
    echo -e "   ${RED}✗${NC} backend/hf_planner.py not updated"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "LOCAL_MODEL_URL" backend/.env 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} backend/.env has LOCAL_MODEL_URL"
else
    echo -e "   ${YELLOW}⚠${NC}  backend/.env missing LOCAL_MODEL_URL (will be set in Render)"
fi

# Check 5: Python availability
echo ""
echo "5. Checking Python environment..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "   ${GREEN}✓${NC} Python ${PYTHON_VERSION} available"
    
    # Check NumPy version
    NUMPY_VERSION=$(python3 -c "import numpy; print(numpy.__version__)" 2>/dev/null)
    if [ $? -eq 0 ]; then
        if [[ $NUMPY_VERSION == 2.* ]]; then
            echo -e "   ${RED}✗${NC} NumPy ${NUMPY_VERSION} - INCOMPATIBLE! Need numpy<2.0.0"
            echo -e "      Run: ./fix_local_env.sh"
            ERRORS=$((ERRORS + 1))
        else
            echo -e "   ${GREEN}✓${NC} NumPy ${NUMPY_VERSION} compatible"
        fi
    else
        echo -e "   ${YELLOW}⚠${NC}  NumPy not installed"
    fi
    
    # Check for bitsandbytes
    python3 -c "import bitsandbytes" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "   ${RED}✗${NC} bitsandbytes found - INCOMPATIBLE with Apple Silicon"
        echo -e "      Run: ./fix_local_env.sh"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "   ${GREEN}✓${NC} bitsandbytes not installed (good)"
    fi
else
    echo -e "   ${RED}✗${NC} Python 3 not found"
    ERRORS=$((ERRORS + 1))
fi

# Check 6: Adapter path in server
echo ""
echo "6. Checking server configuration..."
if grep -q 'ADAPTER_PATH = "training/outputs/qwen25_1_5b_lora_hf"' local_model_server.py 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} Server points to correct adapter path"
else
    echo -e "   ${RED}✗${NC} Server adapter path incorrect"
    ERRORS=$((ERRORS + 1))
fi

if grep -q 'BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"' local_model_server.py 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} Server uses Qwen2.5-1.5B-Instruct"
else
    echo -e "   ${RED}✗${NC} Server base model incorrect"
    ERRORS=$((ERRORS + 1))
fi

# Check 7: Health endpoint
echo ""
echo "7. Checking endpoints..."
if grep -q '@app.get("/health")' local_model_server.py 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} Health endpoint exists"
else
    echo -e "   ${RED}✗${NC} Health endpoint missing"
    ERRORS=$((ERRORS + 1))
fi

if grep -q '@app.post("/parse-query"' local_model_server.py 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} Parse-query endpoint exists"
else
    echo -e "   ${RED}✗${NC} Parse-query endpoint missing"
    ERRORS=$((ERRORS + 1))
fi

# Summary
echo ""
echo "========================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    echo "========================================="
    echo ""
    echo "Ready to test! Run:"
    echo ""
    echo "  1. Install dependencies:"
    echo "     pip install -r requirements_local_server.txt"
    echo ""
    echo "  2. Start local server:"
    echo "     python3 local_model_server.py"
    echo ""
    echo "  3. In another terminal, run tests:"
    echo "     python3 test_local_model.py"
    echo ""
    echo "  4. Expose with ngrok:"
    echo "     ngrok http 8001"
    echo ""
    echo "  5. Deploy to Render with LOCAL_MODEL_URL"
    echo ""
    exit 0
else
    echo -e "${RED}❌ ${ERRORS} CHECK(S) FAILED${NC}"
    echo "========================================="
    echo ""
    echo "Common issues and fixes:"
    echo ""
    echo "  NumPy 2.x incompatibility:"
    echo "    ./fix_local_env.sh"
    echo ""
    echo "  bitsandbytes on Apple Silicon:"
    echo "    ./fix_local_env.sh"
    echo ""
    echo "  Missing dependencies:"
    echo "    pip install -r requirements_local_server.txt"
    echo ""
    echo "For detailed diagnostics:"
    echo "  python3 check_environment.py"
    echo ""
    exit 1
fi
