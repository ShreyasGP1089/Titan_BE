#!/bin/bash

# Production Deployment Helper Script
# Automates the migration and deployment process

set -e  # Exit on error

echo "=============================================================================="
echo "🚀 AI Shopping Search - Production Deployment Helper"
echo "=============================================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install Python 3.10 or 3.11"
        exit 1
    fi
    
    python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    log_info "Python version: $python_version"
    
    # Check Docker (optional)
    if command -v docker &> /dev/null; then
        log_info "Docker found: $(docker --version)"
    else
        log_warn "Docker not found. Docker deployment will not be available."
    fi
    
    echo ""
}

# Menu
show_menu() {
    echo "What would you like to do?"
    echo ""
    echo "  1) Convert MLX adapter to Hugging Face format"
    echo "  2) Retrain model with Hugging Face (recommended for production)"
    echo "  3) Test Hugging Face model locally"
    echo "  4) Deploy with Docker (requires Docker installed)"
    echo "  5) Generate production .env file"
    echo "  6) Run manual installation"
    echo "  7) Exit"
    echo ""
    read -p "Enter choice [1-7]: " choice
    echo ""
}

# Convert MLX to HF
convert_adapter() {
    log_info "Converting MLX adapter to Hugging Face format..."
    
    if [ ! -d "training/outputs/shopping_agent_lora" ]; then
        log_error "MLX adapter not found at training/outputs/shopping_agent_lora"
        log_error "Please train the model with MLX first, or choose option 2 to retrain."
        return 1
    fi
    
    cd training
    python3 convert_mlx_to_hf.py
    cd ..
    
    log_info "✅ Conversion complete!"
    echo ""
}

# Retrain with HF
retrain_hf() {
    log_info "Retraining model with Hugging Face..."
    log_warn "This will take 1-3 hours depending on your hardware."
    
    read -p "Continue? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        log_info "Cancelled."
        return 1
    fi
    
    cd training
    
    # Install dependencies if needed
    if [ ! -d "../venv" ]; then
        log_info "Creating virtual environment..."
        python3 -m venv ../venv
    fi
    
    log_info "Installing dependencies..."
    source ../venv/bin/activate
    pip install -q -r requirements.txt
    pip install -q transformers peft accelerate datasets safetensors
    
    log_info "Starting training..."
    python3 train_hf.py
    
    deactivate
    cd ..
    
    log_info "✅ Training complete!"
    echo ""
}

# Test HF model
test_hf_model() {
    log_info "Testing Hugging Face model..."
    
    if [ ! -d "training/outputs/shopping_agent_lora_hf" ]; then
        log_error "HF adapter not found. Please run option 1 or 2 first."
        return 1
    fi
    
    export USE_HF_PLANNER=true
    
    cd backend
    python3 -c "
from hf_planner import shopping_planner_hf
import json

print('Testing with query: running shoes under 5000')
result = shopping_planner_hf('running shoes under 5000')
print(json.dumps(result, indent=2))
"
    cd ..
    
    log_info "✅ Test complete!"
    echo ""
}

# Deploy with Docker
deploy_docker() {
    log_info "Deploying with Docker..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker first."
        return 1
    fi
    
    if [ ! -d "training/outputs/shopping_agent_lora_hf" ]; then
        log_error "HF adapter not found. Please run option 1 or 2 first."
        return 1
    fi
    
    log_info "Building Docker images..."
    docker-compose build
    
    log_info "Starting services..."
    docker-compose up -d
    
    echo ""
    log_info "✅ Deployment complete!"
    echo ""
    log_info "Services running:"
    docker-compose ps
    echo ""
    log_info "API available at: http://localhost:5000"
    log_info "Health check: curl http://localhost:5000/api/v1/system/health"
    echo ""
}

# Generate .env
generate_env() {
    log_info "Generating production .env file..."
    
    if [ -f "backend/.env" ]; then
        read -p ".env already exists. Overwrite? (y/n): " confirm
        if [ "$confirm" != "y" ]; then
            log_info "Cancelled."
            return 1
        fi
    fi
    
    # Generate random API key
    API_KEY=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-50)
    DB_PASSWORD=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-20)
    
    cat > backend/.env << EOF
# Production Environment Configuration
# Generated: $(date)

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=decathlon_db
POSTGRES_USER=decathlonuser
POSTGRES_PASSWORD=$DB_PASSWORD

# API Authentication
API_KEY=$API_KEY

# Model Configuration (use HF for production Linux)
USE_HF_PLANNER=true

# Hugging Face Cache
HF_HOME=/app/.cache/huggingface
TRANSFORMERS_CACHE=/app/.cache/transformers

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=false

# Logging
LOG_LEVEL=INFO
EOF
    
    log_info "✅ .env file created at backend/.env"
    log_warn "⚠️  IMPORTANT: Save these credentials securely!"
    echo ""
    echo "  API_KEY: $API_KEY"
    echo "  DB_PASSWORD: $DB_PASSWORD"
    echo ""
}

# Manual installation
manual_install() {
    log_info "Starting manual installation..."
    log_warn "This will install dependencies and set up the environment."
    
    read -p "Continue? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        log_info "Cancelled."
        return 1
    fi
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        log_info "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    log_info "Activating virtual environment..."
    source venv/bin/activate
    
    log_info "Installing backend dependencies..."
    pip install -q --upgrade pip
    pip install -q -r backend/requirements_production.txt
    
    log_info "Installing training dependencies..."
    pip install -q -r training/requirements.txt
    
    log_info "✅ Installation complete!"
    echo ""
    log_info "Next steps:"
    echo "  1. Activate venv: source venv/bin/activate"
    echo "  2. Convert/train model: Choose option 1 or 2"
    echo "  3. Run API: cd backend && python api_swagger.py"
    echo ""
}

# Main script
check_prerequisites

while true; do
    show_menu
    case $choice in
        1)
            convert_adapter
            read -p "Press Enter to continue..."
            ;;
        2)
            retrain_hf
            read -p "Press Enter to continue..."
            ;;
        3)
            test_hf_model
            read -p "Press Enter to continue..."
            ;;
        4)
            deploy_docker
            read -p "Press Enter to continue..."
            ;;
        5)
            generate_env
            read -p "Press Enter to continue..."
            ;;
        6)
            manual_install
            read -p "Press Enter to continue..."
            ;;
        7)
            log_info "Exiting. Good luck with your deployment! 🚀"
            exit 0
            ;;
        *)
            log_error "Invalid choice. Please try again."
            read -p "Press Enter to continue..."
            ;;
    esac
    clear
done
