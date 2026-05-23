/**
 * Integris Clinical Platform — Landing Page Runtime Config
 *
 * Swap these values between local dev and production by editing
 * this single file before deploying with deploy.sh.
 *
 * Local dev:
 *   API_BASE_URL  → FastAPI at localhost:8000
 *   APP_URL       → Angular dev server at localhost:4200
 *
 * Production:
 *   API_BASE_URL  → https://api.integris-clinical.com  (Cloud Run)
 *   APP_URL       → https://app.integris-clinical.com  (Cloud Run frontend)
 */
window.INTEGRIS_CONFIG = {
  // Base URL for all API calls (no trailing slash)
  API_BASE_URL: 'http://localhost:8000',

  // Full URL of the Angular application — used by Login / Get Started CTAs
  APP_URL: 'http://localhost:4200',

  // Contact form endpoint (derived from API_BASE_URL — override if needed)
  get CONTACT_URL() {
    return this.API_BASE_URL + '/api/v1/contact';
  },
};
