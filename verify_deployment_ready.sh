#!/bin/bash

# Deployment Readiness Verification Script
# Run this before deploying to Render

echo "╔════════════════════════════════════════════════════════════╗"
echo "║        Deployment Readiness Verification                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

ERRORS=0
WARNINGS=0

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((ERRORS++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

echo "═══════════════════════════════════════════════════════════"
echo "1. File Structure"
echo "═══════════════════════════════════════════════════════════"

# Check critical files exist
if [ -f "backend/api_swagger.py" ]; then
    check_pass "backend/api_swagger.py exists"
else
    check_fail "backend/api_swagger.py missing"
fi

if [ -f "backend/hf_planner.py" ]; then
    check_pass "backend/hf_planner.py exists"
else
    check_fail "backend/hf_planner.py missing"
fi

if [ -f "backend/requirements_production.txt" ]; then
    check_pass "backend/requirements_production.txt exists"
else
    check_fail "backend/requirements_production.txt missing"
fi

if [ -f "Dockerfile" ]; then
    check_pass "Dockerfile exists"
else
    check_fail "Dockerfile missing"
fi

if [ -f "docker-compose.yml" ]; then
    check_pass "docker-compose.yml exists"
else
    check_fail "docker-compose.yml missing"
fi

if [ -f ".gitignore" ]; then
    check_pass ".gitignore exists"
else
    check_warn ".gitignore missing (secrets may be exposed)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "2. Dependencies Check"
echo "═══════════════════════════════════════════════════════════"

# Check for MLX in production requirements (should NOT exist)
if grep -q "^mlx" backend/requirements_production.txt; then
    check_fail "MLX found in requirements_production.txt (not Linux-compatible)"
else
    check_pass "No MLX dependencies in production requirements"
fi

# Check for essential packages
if grep -q "transformers" backend/requirements_production.txt; then
    check_pass "transformers found in requirements"
else
    check_fail "transformers missing from requirements"
fi

if grep -q "flask" backend/requirements_production.txt; then
    check_pass "flask found in requirements"
else
    check_fail "flask missing from requirements"
fi

if grep -q "gunicorn" backend/requirements_production.txt; then
    check_pass "gunicorn found in requirements"
else
    check_fail "gunicorn missing from requirements (needed for production)"
fi

# Check PEFT is commented out
if grep -q "^peft" backend/requirements_production.txt; then
    check_warn "PEFT is enabled (may cause loading issues, should be commented out)"
else
    check_pass "PEFT is commented out (using base model)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "3. Code Quality Checks"
echo "═══════════════════════════════════════════════════════════"

# Check hf_planner.py doesn't import peft
if grep -q "from peft import" backend/hf_planner.py; then
    check_warn "hf_planner.py imports PEFT (should be removed for base model)"
else
    check_pass "hf_planner.py doesn't import PEFT"
fi

# Check for MLX imports in backend (should NOT exist)
if grep -rq "import mlx" backend/*.py 2>/dev/null; then
    check_fail "MLX imports found in backend code"
else
    check_pass "No MLX imports in backend code"
fi

# Check USE_HF_PLANNER is set in docker-compose
if grep -q "USE_HF_PLANNER.*true" docker-compose.yml; then
    check_pass "USE_HF_PLANNER=true in docker-compose.yml"
else
    check_warn "USE_HF_PLANNER not set to true in docker-compose.yml"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "4. Security Checks"
echo "═══════════════════════════════════════════════════════════"

# Check if .env is in .gitignore
if [ -f ".gitignore" ] && grep -q "\.env" .gitignore; then
    check_pass ".env is excluded in .gitignore"
else
    check_fail ".env not excluded in .gitignore (security risk)"
fi

# Check if .env file exists (should exist locally, but warned if exposed)
if [ -f "backend/.env" ]; then
    check_warn "backend/.env exists locally (ensure it's not committed to git)"
    
    # Check if API key looks exposed (default test key)
    if grep -q "decathlon_smart_search_2024_secure_key_abc123xyz" backend/.env 2>/dev/null; then
        check_fail "Default API key found in .env (THIS WAS EXPOSED IN GIT - MUST ROTATE)"
    fi
else
    check_warn "backend/.env not found (will need to create for local testing)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "5. Docker Configuration"
echo "═══════════════════════════════════════════════════════════"

# Check Dockerfile uses gunicorn
if grep -q "gunicorn" Dockerfile; then
    check_pass "Dockerfile uses gunicorn"
else
    check_warn "Dockerfile doesn't use gunicorn (may not be production-ready)"
fi

# Check Dockerfile exposes port
if grep -q "EXPOSE" Dockerfile; then
    check_pass "Dockerfile exposes port"
else
    check_warn "Dockerfile doesn't expose port"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "6. Documentation"
echo "═══════════════════════════════════════════════════════════"

if [ -f "DEPLOYMENT_STATUS.md" ]; then
    check_pass "DEPLOYMENT_STATUS.md exists"
else
    check_warn "DEPLOYMENT_STATUS.md missing"
fi

if [ -f "DEPLOY_CHECKLIST.md" ]; then
    check_pass "DEPLOY_CHECKLIST.md exists"
else
    check_warn "DEPLOY_CHECKLIST.md missing"
fi

if [ -f "README.md" ]; then
    check_pass "README.md exists"
else
    check_warn "README.md missing"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "SUMMARY"
echo "═══════════════════════════════════════════════════════════"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ ALL CHECKS PASSED${NC}"
    echo ""
    echo "Your application is ready for deployment! 🚀"
    echo ""
    echo "Next steps:"
    echo "  1. Rotate API key (see DEPLOY_CHECKLIST.md)"
    echo "  2. Test locally: docker-compose up"
    echo "  3. Deploy to Render following DEPLOY_CHECKLIST.md"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ PASSED WITH WARNINGS${NC}"
    echo ""
    echo "Errors: $ERRORS"
    echo "Warnings: $WARNINGS"
    echo ""
    echo "Your application can be deployed, but review warnings above."
    echo "See DEPLOY_CHECKLIST.md for deployment instructions."
    exit 0
else
    echo -e "${RED}✗ FAILED${NC}"
    echo ""
    echo "Errors: $ERRORS"
    echo "Warnings: $WARNINGS"
    echo ""
    echo "Fix the errors above before deploying."
    echo "See DEPLOYMENT_STATUS.md for troubleshooting."
    exit 1
fi
