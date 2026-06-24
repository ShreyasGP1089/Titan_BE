#!/bin/bash
# Test script for the new unified API

API_URL="http://localhost:5000/api/v1"
API_KEY="decathlon_smart_search_2024_secure_key_abc123xyz"

echo "========================================="
echo "Testing Decathlon Smart Shopping API"
echo "========================================="
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "--------------------"
curl -s "${API_URL}/system/health" | python3 -m json.tool
echo ""
echo ""

# Test 2: Search Intent
echo "Test 2: Search Intent - running shoes under 5000"
echo "------------------------------------------------"
curl -s -X POST "${API_URL}/query" \
  -H "Api-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query":"running shoes under 5000"}' | python3 -m json.tool
echo ""
echo ""

# Test 3: Task Intent
echo "Test 3: Task Intent - golf equipment"
echo "------------------------------------"
curl -s -X POST "${API_URL}/query" \
  -H "Api-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query":"I want to start playing golf"}' | python3 -m json.tool
echo ""
echo ""

# Test 4: Compare Intent
echo "Test 4: Compare Intent (if products exist)"
echo "------------------------------------------"
curl -s -X POST "${API_URL}/query" \
  -H "Api-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query":"compare MH500 and NH500"}' | python3 -m json.tool
echo ""
echo ""

# Test 5: Alternatives Intent
echo "Test 5: Alternatives Intent (if product exists)"
echo "-----------------------------------------------"
curl -s -X POST "${API_URL}/query" \
  -H "Api-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query":"alternatives to MH500"}' | python3 -m json.tool
echo ""
echo ""

echo "========================================="
echo "Testing Complete"
echo "========================================="
