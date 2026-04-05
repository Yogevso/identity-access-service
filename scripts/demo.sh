#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# Identity Access Service — Live Demo Script
# Run: bash scripts/demo.sh
# Requires: curl, jq, server running on :8003 (or docker compose up)
# ──────────────────────────────────────────────────────────────────

set -euo pipefail
API="http://localhost:8003/api/v1"
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

step() { echo -e "\n${BOLD}${CYAN}═══ $1 ═══${NC}\n"; }
info() { echo -e "${GREEN}→${NC} $1"; }
warn() { echo -e "${YELLOW}→${NC} $1"; }
wait_for() { sleep "${1:-1}"; }

# ── 1. Health Check ──────────────────────────────────────────────
step "1/7  Health Check"
curl -s "$API/health" | jq .
info "IAM service + database healthy"

# ── 2. Register a Tenant ─────────────────────────────────────────
step "2/7  Register a Tenant + Admin User"
SIGNUP=$(curl -s -X POST "$API/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "Demo Corp",
    "tenant_slug": "demo-corp",
    "email": "admin@demo-corp.io",
    "password": "SecurePass123!"
  }')
echo "$SIGNUP" | jq '{tenant_id: .tenant.id, user_email: .user.email, role: .user.role}'
info "Tenant created with TENANT_ADMIN user"

# ── 3. Login ─────────────────────────────────────────────────────
step "3/7  Login → JWT + Refresh Token"
LOGIN=$(curl -s -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "demo-corp",
    "email": "admin@demo-corp.io",
    "password": "SecurePass123!"
  }')
ACCESS_TOKEN=$(echo "$LOGIN" | jq -r '.access_token')
REFRESH_TOKEN=$(echo "$LOGIN" | jq -r '.refresh_token')
echo "$LOGIN" | jq '{token_type, access_token: (.access_token | .[0:20] + "..."), refresh_token: (.refresh_token | .[0:20] + "...")}'
info "Short-lived JWT + rotatable refresh token issued"

# ── 4. Who Am I ──────────────────────────────────────────────────
step "4/7  Who Am I (JWT Introspection)"
curl -s "$API/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '{email, role, tenant_id}'
info "JWT decoded — role and tenant from token claims"

# ── 5. Refresh Token Rotation ────────────────────────────────────
step "5/7  Refresh Token Rotation"
REFRESH=$(curl -s -X POST "$API/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")
NEW_ACCESS=$(echo "$REFRESH" | jq -r '.access_token')
echo "$REFRESH" | jq '{new_access: (.access_token | .[0:20] + "..."), new_refresh: (.refresh_token | .[0:20] + "...")}'
info "Old refresh token invalidated — new pair issued"
ACCESS_TOKEN="$NEW_ACCESS"

# ── 6. RBAC — Forbidden Access ───────────────────────────────────
step "6/7  RBAC Enforcement"
info "Attempting system-admin endpoint as tenant-admin..."
RESP=$(curl -s -o /dev/null -w "%{http_code}" "$API/admin/tenants" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
if [ "$RESP" = "403" ]; then
  echo -e "${RED}403 Forbidden${NC} — tenant admin cannot access system-admin routes"
  info "RBAC correctly enforced"
else
  echo "Response: $RESP"
fi

# ── 7. Audit Log ─────────────────────────────────────────────────
step "7/7  Audit Log"
curl -s "$API/audit-logs?limit=5" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '[.data[:3][] | {action, actor_email, timestamp}]'
info "Every auth and admin action is logged"

# ── Cleanup ──────────────────────────────────────────────────────
echo ""
info "Logging out..."
curl -s -X POST "$API/auth/logout" \
  -H "Authorization: Bearer $ACCESS_TOKEN" > /dev/null 2>&1 || true

echo ""
echo -e "${BOLD}Demo complete${NC} — Identity Access Service: register → login → JWT → RBAC → audit"
