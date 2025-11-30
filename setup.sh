#!/bin/bash
# SmartStoreDB Setup Script for Linux/Mac
# Run this script: chmod +x setup.sh && ./setup.sh

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                           ║${NC}"
echo -e "${CYAN}║        SmartStoreDB Automated Setup (Linux/Mac)          ║${NC}"
echo -e "${CYAN}║                                                           ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Functions
print_step() {
    echo ""
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "  ${GREEN}✓ $1${NC}"
}

print_failure() {
    echo -e "  ${RED}✗ $1${NC}"
}

print_info() {
    echo -e "  ${BLUE}ℹ $1${NC}"
}

# Check prerequisites
print_step "Checking Prerequisites..."

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 12 ]; then
        print_success "Python $PYTHON_VERSION found"
        PYTHON_CMD="python3"
    else
        print_failure "Python 3.12+ required (found $PYTHON_VERSION)"
        print_info "Download from: https://www.python.org/downloads/"
        exit 1
    fi
else
    print_failure "Python not found"
    print_info "Download from: https://www.python.org/downloads/"
    exit 1
fi

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version 2>&1 | sed 's/v//')
    NODE_MAJOR=$(echo $NODE_VERSION | cut -d. -f1)
    
    if [ "$NODE_MAJOR" -ge 18 ]; then
        print_success "Node.js $NODE_VERSION found"
    else
        print_failure "Node.js 18+ required (found $NODE_VERSION)"
        print_info "Download from: https://nodejs.org/"
        exit 1
    fi
else
    print_failure "Node.js not found"
    print_info "Download from: https://nodejs.org/"
    exit 1
fi

# Check Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version 2>&1)
    print_success "Docker found"
else
    print_failure "Docker not found"
    print_info "Install: https://docs.docker.com/get-docker/"
    exit 1
fi

# Create virtual environment
print_step "Creating Python Virtual Environment..."
if [ -d ".venv" ]; then
    print_info "Virtual environment already exists"
else
    $PYTHON_CMD -m venv .venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
print_step "Activating Virtual Environment..."
source .venv/bin/activate
print_success "Virtual environment activated"

# Upgrade pip
print_step "Upgrading pip..."
$PYTHON_CMD -m pip install --upgrade pip --quiet
print_success "pip upgraded"

# Install Python dependencies
print_step "Installing Python Dependencies..."
print_info "This may take 5-10 minutes..."
pip install -r requirements.txt --quiet
print_success "Python dependencies installed"

# Setup Redis
print_step "Setting up Redis..."
if [ "$(docker ps -q -f name=smartstore-redis -f status=running)" ]; then
    print_info "Redis already running"
else
    # Stop existing container if any
    docker stop smartstore-redis 2>/dev/null || true
    docker rm smartstore-redis 2>/dev/null || true
    
    # Pull and run Redis
    print_info "Pulling Redis image..."
    docker pull redis:alpine --quiet
    print_info "Starting Redis container..."
    docker run -d --name smartstore-redis -p 6379:6379 redis:alpine > /dev/null
    print_success "Redis started on port 6379"
fi

# Setup frontend
print_step "Installing Frontend Dependencies..."
cd frontend
npm install --silent
print_success "Frontend dependencies installed"
cd ..

# Create directories
print_step "Creating Data Directories..."
mkdir -p data/models data/archive data/wal
print_success "Data directories created"

# Create .env file
print_step "Creating Environment Configuration..."
if [ -f ".env" ]; then
    print_info ".env file already exists (keeping existing)"
else
    SECRET_KEY=$(openssl rand -hex 32)
    cat > .env << EOF
DATABASE_URL=./data/smartstore.db
REDIS_HOST=localhost
REDIS_PORT=6379
SECRET_KEY=$SECRET_KEY
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

LSTM_EPOCHS=50
LSTM_BATCH_SIZE=32
LSTM_SEQUENCE_LENGTH=10

CACHE_MODEL_FILE=./data/models/lstm_cache_predictor.h5
ANOMALY_MODEL_FILE=./data/models/isolation_forest.pkl
PROPHET_MODEL_FILE=./data/models/prophet_forecaster.pkl
DBSCAN_MODEL_FILE=./data/models/dbscan_clusterer.pkl

IFOREST_CONTAMINATION=0.1
IFOREST_N_ESTIMATORS=100
DBSCAN_EPS=0.5
DBSCAN_MIN_SAMPLES=5
EOF
    print_success ".env file created with random SECRET_KEY"
fi

# Initialize database
print_step "Initializing Database..."
$PYTHON_CMD -c "from webapp.repository import repository; repository.get_stats()" 2>&1 > /dev/null
print_success "Database initialized"

# Ask about ML training
print_step "Machine Learning Models Setup"
echo ""
echo -e "  ML models provide predictive caching, anomaly detection, and forecasting."
echo -e "  Training takes approximately 20-30 minutes."
echo ""
read -p "  Do you want to train ML models now? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_step "Training ML Models..."
    print_info "This will take 20-30 minutes. Please be patient..."
    $PYTHON_CMD train_all_models.py
else
    print_info "Skipping ML training (you can run 'python train_all_models.py' later)"
    print_info "ML endpoints will return mock data until models are trained"
fi

# Final summary
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                           ║${NC}"
echo -e "${GREEN}║                 SETUP COMPLETE!                           ║${NC}"
echo -e "${GREEN}║                                                           ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo ""
echo -e "${NC}1. Start Backend (Terminal 1):${NC}"
echo -e "   ${BLUE}source .venv/bin/activate${NC}"
echo -e "   ${BLUE}cd webapp${NC}"
echo -e "   ${BLUE}uvicorn main:app --reload --host 0.0.0.0 --port 8000${NC}"
echo ""
echo -e "${NC}2. Start Frontend (Terminal 2):${NC}"
echo -e "   ${BLUE}cd frontend${NC}"
echo -e "   ${BLUE}npm run dev${NC}"
echo ""
echo -e "${NC}3. Start CLI (Terminal 3, Optional):${NC}"
echo -e "   ${BLUE}source .venv/bin/activate${NC}"
echo -e "   ${BLUE}python -m smartstoredb.main${NC}"
echo ""
echo -e "${CYAN}Access Points:${NC}"
echo -e "  ${YELLOW}- Frontend:  http://localhost:3001${NC}"
echo -e "  ${YELLOW}- API Docs:  http://localhost:8000/api/v1/docs${NC}"
echo -e "  ${YELLOW}- Login:     admin / admin123  or  user / user123${NC}"
echo ""
echo -e "${CYAN}Run Tests:${NC}"
echo -e "  ${BLUE}python test_integration.py${NC}"
echo ""
echo -e "${NC}For help, see README.md${NC}"
echo ""
