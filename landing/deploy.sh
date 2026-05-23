#!/usr/bin/env bash
# =============================================================================
# Integris Landing Page — GCP Cloud Storage deploy
#
# Prerequisites:
#   gcloud auth login
#   gcloud config set project YOUR_GCP_PROJECT_ID
#
# Usage:
#   BUCKET=integris-landing-prod ./deploy.sh
#   BUCKET=integris-landing-prod ENV=production ./deploy.sh
#
# The ENV variable swaps the API base URL in config.js before upload.
# Defaults to "development" (localhost) if not set.
# =============================================================================
set -euo pipefail

BUCKET="${BUCKET:?'Set BUCKET to your GCS bucket name, e.g. BUCKET=integris-landing-prod'}"
ENV="${ENV:-development}"
REGION="${REGION:-us-central1}"

echo ""
echo "  Integris Landing Page Deploy"
echo "  ──────────────────────────────────────"
echo "  Bucket  : gs://${BUCKET}"
echo "  Env     : ${ENV}"
echo ""

# ── 1. Patch config.js for the target environment ─────────────────────────────
cp config.js config.js.bak

if [[ "${ENV}" == "production" ]]; then
  cat > config.js <<'EOF'
window.INTEGRIS_CONFIG = {
  API_BASE_URL: 'https://api.integris-clinical.com',
  APP_URL:      'https://app.integris-clinical.com',
  get CONTACT_URL() { return this.API_BASE_URL + '/api/v1/contact'; },
};
EOF
  echo "  config.js patched for production"
elif [[ "${ENV}" == "staging" ]]; then
  cat > config.js <<'EOF'
window.INTEGRIS_CONFIG = {
  API_BASE_URL: 'https://api-staging.integris-clinical.com',
  APP_URL:      'https://app-staging.integris-clinical.com',
  get CONTACT_URL() { return this.API_BASE_URL + '/api/v1/contact'; },
};
EOF
  echo "  config.js patched for staging"
else
  echo "  config.js left as-is (development / local)"
fi

# ── 2. Sync files to GCS (delete stale files, preserve metadata) ──────────────
echo ""
echo "  Syncing to gs://${BUCKET} ..."

gsutil -m rsync -r -d \
  -x "^\..*|.*\.bak$|^deploy\.sh$" \
  . "gs://${BUCKET}"

# ── 3. Set cache headers ───────────────────────────────────────────────────────
# HTML: no-cache (always revalidate)
gsutil -m setmeta -h "Cache-Control:no-cache, no-store, must-revalidate" \
  "gs://${BUCKET}/index.html" 2>/dev/null || true

# Hashed assets (JS, SVG, CSS): 1-year immutable
gsutil -m setmeta -h "Cache-Control:public, max-age=31536000, immutable" \
  "gs://${BUCKET}/assets/**" 2>/dev/null || true

gsutil setmeta -h "Cache-Control:no-cache" \
  "gs://${BUCKET}/config.js" 2>/dev/null || true

# ── 4. Restore original config.js ─────────────────────────────────────────────
mv config.js.bak config.js

echo ""
echo "  ✓ Deploy complete"
echo "  Landing page: https://storage.googleapis.com/${BUCKET}/index.html"
echo "  (or your custom domain if CNAME is configured)"
echo ""
