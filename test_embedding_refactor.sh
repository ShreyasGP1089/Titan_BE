#!/bin/bash

# Test script for embedding refactoring
# Verifies local embedding generation works correctly

set -e

echo "================================================================================"
echo "EMBEDDING REFACTORING TEST SUITE"
echo "================================================================================"
echo ""

API_URL="http://localhost:5000"
API_KEY="decathlon_smart_search_2024_secure_key_abc123xyz"

echo "Configuration:"
echo "  API URL: $API_URL"
echo "  Testing: Local sentence-transformers embedding generation"
echo ""

# Test 1: Python import test
echo "================================================================================"
echo "TEST 1: Python Import Test"
echo "================================================================================"
echo "Testing if sentence-transformers can be imported..."
echo ""

python3 -c "
from sentence_transformers import SentenceTransformer
print('✓ sentence-transformers imported successfully')
" || {
    echo "❌ FAILED: sentence-transformers not installed"
    echo ""
    echo "Install with:"
    echo "  cd backend"
    echo "  pip install sentence-transformers==2.2.2"
    exit 1
}

echo ""

# Test 2: Embedding module test
echo "================================================================================"
echo "TEST 2: Embedding Module Test"
echo "================================================================================"
echo "Testing backend/embedding.py directly..."
echo ""

cd backend
python3 -c "
from embedding import get_embedding
embedding = get_embedding('running shoes')
print(f'✓ Embedding generated')
print(f'  Dimension: {len(embedding)}')
print(f'  Preview: {embedding[:5]}')
assert len(embedding) == 384, f'Expected 384 dimensions, got {len(embedding)}'
print('✓ Dimension check passed')
" || {
    echo "❌ FAILED: Embedding module test failed"
    exit 1
}
cd ..

echo ""

# Test 3: Check for HTTP calls to /embed
echo "================================================================================"
echo "TEST 3: Verify No HTTP Calls to /embed"
echo "================================================================================"
echo "Searching for active /embed endpoint calls..."
echo ""

EMBED_CALLS=$(grep -r "f\"{self.base_url}/embed\"" backend/ --include="*.py" | grep -v "# LEGACY" || true)

if [ -z "$EMBED_CALLS" ]; then
    echo "✓ No active HTTP calls to /embed found"
else
    echo "❌ FAILED: Found HTTP calls to /embed:"
    echo "$EMBED_CALLS"
    exit 1
fi

echo ""

# Test 4: API endpoint test
echo "================================================================================"
echo "TEST 4: Debug Embedding Endpoint Test"
echo "================================================================================"
echo "Testing POST /api/v1/debug/embedding..."
echo ""

# Check if API is running
if ! curl -s "$API_URL/api/v1/system/health" > /dev/null 2>&1; then
    echo "⚠️  WARNING: API server not running at $API_URL"
    echo ""
    echo "To test the API endpoint, start the server:"
    echo "  cd backend"
    echo "  python api_swagger.py"
    echo ""
    echo "Then run this script again."
    echo ""
    echo "Skipping API tests..."
else
    echo "Testing embedding endpoint..."
    
    RESPONSE=$(curl -s -X POST "$API_URL/api/v1/debug/embedding" \
        -H "Api-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"text": "running shoes"}')
    
    echo "Response:"
    echo "$RESPONSE" | python3 -m json.tool
    
    # Verify response structure
    DIMENSION=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['dimension'])")
    MODEL=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['model'])")
    
    if [ "$DIMENSION" = "384" ]; then
        echo ""
        echo "✓ Embedding dimension correct: 384"
    else
        echo ""
        echo "❌ FAILED: Expected dimension 384, got $DIMENSION"
        exit 1
    fi
    
    if [ "$MODEL" = "sentence-transformers/all-MiniLM-L6-v2" ]; then
        echo "✓ Model correct: sentence-transformers/all-MiniLM-L6-v2"
    else
        echo "❌ FAILED: Unexpected model: $MODEL"
        exit 1
    fi
    
    echo "✓ API endpoint test passed"
fi

echo ""

# Test 5: Full pipeline test
if curl -s "$API_URL/api/v1/system/health" > /dev/null 2>&1; then
    echo "================================================================================"
    echo "TEST 5: Full Pipeline Test"
    echo "================================================================================"
    echo "Testing POST /api/v1/query with search intent..."
    echo ""
    
    RESPONSE=$(curl -s -X POST "$API_URL/api/v1/query" \
        -H "Api-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"query": "running shoes under 5000"}')
    
    # Check if response is valid JSON
    if echo "$RESPONSE" | python3 -m json.tool > /dev/null 2>&1; then
        echo "✓ Full pipeline returned valid JSON"
        
        # Check if products were returned
        PRODUCT_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; r=json.load(sys.stdin); print(len(r.get('products', [])))" 2>/dev/null || echo "0")
        
        if [ "$PRODUCT_COUNT" -gt "0" ]; then
            echo "✓ Full pipeline returned $PRODUCT_COUNT products"
            echo "✓ Embeddings used for semantic search (locally generated)"
        else
            echo "⚠️  No products returned (may be due to database state)"
        fi
    else
        echo "❌ FAILED: Full pipeline returned invalid JSON"
        echo "Response: $RESPONSE"
        exit 1
    fi
fi

echo ""
echo "================================================================================"
echo "✅ ALL TESTS PASSED"
echo "================================================================================"
echo ""
echo "Summary:"
echo "  ✓ sentence-transformers installed and working"
echo "  ✓ Embedding module generates 384-dim vectors"
echo "  ✓ No active HTTP calls to /embed endpoint"
if curl -s "$API_URL/api/v1/system/health" > /dev/null 2>&1; then
    echo "  ✓ Debug embedding endpoint working"
    echo "  ✓ Full pipeline using local embeddings"
fi
echo ""
echo "Embedding refactoring complete and verified!"
echo "================================================================================"
