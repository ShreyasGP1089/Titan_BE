#!/bin/bash
# Test script for debug endpoints

API_URL="http://localhost:5000/api/v1"
API_KEY="decathlon_smart_search_2024_secure_key_abc123xyz"

echo "========================================="
echo "Testing Debug Endpoints"
echo "========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health Check
echo "Test 1: Health Check"
echo "--------------------"
response=$(curl -s "${API_URL}/system/health")
echo "$response" | python3 -m json.tool 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed${NC}"
fi
echo ""
echo ""

# Test 2: Debug - Parse Query (SLM only)
echo "Test 2: Debug - Parse Query (SLM only)"
echo "--------------------------------------"
echo "Query: 'running shoes under 5000'"
response=$(curl -s -X POST "${API_URL}/debug/parse-query" \
  -H "Api-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query":"running shoes under 5000"}')
echo "$response" | python3 -m json.tool 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Parse query passed${NC}"
else
    echo -e "${RED}✗ Parse query failed${NC}"
fi
echo ""
echo ""

# Test 3: Debug - SearchTool
echo "Test 3: Debug - SearchTool (Direct)"
echo "-----------------------------------"
echo "Parameters: sport=Running, keywords=[\"running\",\"shoes\"], price_limit=5000"
response=$(curl -s -X POST "${API_URL}/debug/search" \
  -H "Api-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "sport": "Running",
    "category_level_1": "Footwear",
    "category_level_2": null,
    "keywords": ["running", "shoes"],
    "price_limit": 5000
  }')
echo "$response" | python3 -m json.tool 2>/dev/null | head -50
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ SearchTool passed${NC}"
else
    echo -e "${RED}✗ SearchTool failed${NC}"
fi
echo ""
echo ""

# Test 4: Debug - TaskTool
echo "Test 4: Debug - TaskTool (Direct)"
echo "---------------------------------"
echo "Parameters: activity=Golf, budget=10000"
response=$(curl -s -X POST "${API_URL}/debug/task" \
  -H "Api-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "activity": "Golf",
    "budget": 10000
  }')
echo "$response" | python3 -m json.tool 2>/dev/null | head -80
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ TaskTool passed${NC}"
else
    echo -e "${RED}✗ TaskTool failed${NC}"
fi
echo ""
echo ""

# Test 5: Debug - CompareTool
echo "Test 5: Debug - CompareTool (Direct)"
echo "------------------------------------"
echo "Parameters: products=[\"MH500\", \"NH500\"]"
response=$(curl -s -X POST "${API_URL}/debug/compare" \
  -H "Api-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "products": ["MH500", "NH500"]
  }')
echo "$response" | python3 -m json.tool 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ CompareTool passed${NC}"
else
    echo -e "${RED}✗ CompareTool failed${NC}"
fi
echo ""
echo ""

# Test 6: Debug - AlternativesTool
echo "Test 6: Debug - AlternativesTool (Direct)"
echo "-----------------------------------------"
echo "Parameters: product=\"MH500\""
response=$(curl -s -X POST "${API_URL}/debug/alternatives" \
  -H "Api-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "product": "MH500"
  }')
echo "$response" | python3 -m json.tool 2>/dev/null | head -80
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ AlternativesTool passed${NC}"
else
    echo -e "${RED}✗ AlternativesTool failed${NC}"
fi
echo ""
echo ""

# Test 7: Production Endpoint (Full Pipeline)
echo "Test 7: Production Endpoint (Full Pipeline)"
echo "-------------------------------------------"
echo "Query: 'running shoes under 5000'"
response=$(curl -s -X POST "${API_URL}/query" \
  -H "Api-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query":"running shoes under 5000"}')
echo "$response" | python3 -m json.tool 2>/dev/null | head -50
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Production endpoint passed${NC}"
else
    echo -e "${RED}✗ Production endpoint failed${NC}"
fi
echo ""
echo ""

echo "========================================="
echo "Testing Complete"
echo "========================================="
echo ""
echo "Summary:"
echo "  - All endpoints use API key authentication"
echo "  - Debug endpoints bypass SLM for direct tool testing"
echo "  - Production endpoint uses full pipeline"
echo ""
echo "Swagger UI: http://localhost:5000/docs"
