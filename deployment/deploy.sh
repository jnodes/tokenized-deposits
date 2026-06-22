#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# deploy.sh -- One-Command Deployment for Cari Network Platform
# Tokenized Deposit Platform | Azure AKS
#
# Usage:
#   ./deploy.sh --env=prividium-testnet     # Deploy to Azure AKS testnet
#   ./deploy.sh --env=prividium-mainnet     # Deploy to Azure AKS mainnet
#   ./deploy.sh --env=local                 # Local Docker Compose
#   ./deploy.sh --env=prividium-mainnet --skip-tests  # Emergency deploy
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ── Configuration ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HELM_CHART="$SCRIPT_DIR/helm/cari-platform"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

ENV=""
SKIP_TESTS=false
DRY_RUN=false
VERSION=$(git describe --tags --always 2>/dev/null || echo "dev")

# Azure-specific configuration
AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-mt-digital-assets}"

# ── Parse Arguments ───────────────────────────────────────────
for arg in "$@"; do
    case $arg in
        --env=*)
            ENV="${arg#*=}"
            ;;
        --skip-tests)
            SKIP_TESTS=true
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        --version=*)
            VERSION="${arg#*=}"
            ;;
        --help|-h)
            echo "Usage: ./deploy.sh --env=<environment> [options]"
            echo ""
            echo "Environments:"
            echo "  local                  Docker Compose (development)"
            echo "  prividium-testnet      Azure AKS testnet deployment"
            echo "  prividium-mainnet      Azure AKS mainnet deployment"
            echo ""
            echo "Options:"
            echo "  --skip-tests           Skip test suite (emergency only)"
            echo "  --dry-run              Show what would be deployed"
            echo "  --version=<tag>        Specify image version tag"
            echo "  --help                 Show this help"
            echo ""
            echo "Environment Variables:"
            echo "  AZURE_RESOURCE_GROUP   Azure resource group (default: mt-digital-assets)"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $arg${NC}"
            exit 1
            ;;
    esac
done

if [[ -z "$ENV" ]]; then
    echo -e "${RED}Error: --env is required${NC}"
    echo "Usage: ./deploy.sh --env=<local|prividium-testnet|prividium-mainnet>"
    exit 1
fi

# ── Functions ─────────────────────────────────────────────────
log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

banner() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Cari Deposit Platform on Azure AKS                    ║${NC}"
    echo -e "${BLUE}║  Deployment: ${GREEN}$ENV${BLUE}                                     ║${NC}"
    echo -e "${BLUE}║  Version:    ${GREEN}$VERSION${BLUE}                                        ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

run_tests() {
    if [[ "$SKIP_TESTS" == true ]]; then
        log_warn "Tests SKIPPED (--skip-tests flag). Use only for emergencies."
        return 0
    fi

    log_info "Running full test suite..."
    cd "$PROJECT_ROOT"

    # Quest 2 + Quest 3 tests
    PYTHONPATH=. python -m pytest offchain/tests/ tests/compliance/ -v --tb=short
    local exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        log_error "Tests failed. Aborting deployment."
        exit 1
    fi

    log_ok "All tests passed (119/119)"
}

deploy_local() {
    log_info "Deploying locally with Docker Compose..."

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would run: docker-compose up -d"
        return 0
    fi

    cd "$SCRIPT_DIR"
    docker-compose -f "$COMPOSE_FILE" up -d --build

    log_info "Waiting for API to be healthy..."
    local retries=30
    while [[ $retries -gt 0 ]]; do
        if curl -sf http://localhost:8000/healthz > /dev/null 2>&1; then
            log_ok "API is healthy at http://localhost:8000"
            log_ok "Grafana at http://localhost:3000 (admin/cari_admin)"
            log_ok "Prometheus at http://localhost:9090"
            return 0
        fi
        retries=$((retries - 1))
        sleep 2
    done

    log_error "API failed to become healthy within 60 seconds"
    exit 1
}

deploy_kubernetes() {
    local target_env=$1
    local namespace="cari-${target_env}"
    local values_file="$HELM_CHART/values-${target_env}.yaml"

    if [[ ! -f "$values_file" ]]; then
        log_error "Values file not found: $values_file"
        exit 1
    fi

    log_info "Deploying to Azure AKS: $target_env (namespace: $namespace)"

    # Pre-flight checks
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Install: https://kubernetes.io/docs/tasks/tools/"
        exit 1
    fi

    if ! command -v helm &> /dev/null; then
        log_error "helm not found. Install: https://helm.sh/docs/intro/install/"
        exit 1
    fi

    # Get Azure AKS credentials (comment shows manual step if needed)
    # az aks get-credentials --resource-group $AZURE_RESOURCE_GROUP --name mt-cari-aks-$target_env

    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Azure AKS cluster. Check kubeconfig or run:"
        log_error "  az aks get-credentials --resource-group $AZURE_RESOURCE_GROUP --name <aks-cluster-name>"
        exit 1
    fi

    # Mainnet safety check
    if [[ "$target_env" == "prividium-mainnet" ]]; then
        echo ""
        log_warn "You are deploying to PRODUCTION (prividium-mainnet)"
        read -p "Type 'DEPLOY MAINNET' to confirm: " confirm
        if [[ "$confirm" != "DEPLOY MAINNET" ]]; then
            log_error "Mainnet deployment cancelled."
            exit 1
        fi
    fi

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Helm template output:"
        helm template cari-platform "$HELM_CHART" \
            --namespace "$namespace" \
            --set image.tag="$VERSION" \
            --values "$values_file"
        return 0
    fi

    # Deploy
    helm upgrade --install cari-platform "$HELM_CHART" \
        --namespace "$namespace" \
        --create-namespace \
        --set image.tag="$VERSION" \
        --values "$values_file" \
        --wait \
        --timeout 300s

    log_ok "Helm release deployed successfully"

    # Verify
    log_info "Verifying deployment..."
    kubectl -n "$namespace" rollout status deployment/cari-api --timeout=120s

    # Show status
    echo ""
    log_ok "Deployment complete!"
    kubectl -n "$namespace" get pods -l app=cari-platform
    echo ""
    kubectl -n "$namespace" get svc cari-api
}

# ── Main ──────────────────────────────────────────────────────
banner

# Step 1: Run tests
run_tests

# Step 2: Deploy based on environment
case "$ENV" in
    local)
        deploy_local
        ;;
    prividium-testnet)
        deploy_kubernetes "prividium-testnet"
        ;;
    prividium-mainnet)
        deploy_kubernetes "prividium-mainnet"
        ;;
    *)
        log_error "Unknown environment: $ENV"
        echo "Valid environments: local, prividium-testnet, prividium-mainnet"
        exit 1
        ;;
esac

echo ""
log_ok "═══════════════════════════════════════════════════════"
log_ok "  Deployment to $ENV completed successfully"
log_ok "  Version: $VERSION"
log_ok "═══════════════════════════════════════════════════════"
