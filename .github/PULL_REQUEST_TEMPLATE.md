## Summary

<!-- One paragraph explaining what this PR does and why. Link to the issue it closes.
     Closes #___  -->

## Type of Change

- [ ] `feat` — New feature
- [ ] `fix` — Bug fix
- [ ] `perf` — Performance improvement
- [ ] `refactor` — Code change without behavior change
- [ ] `test` — Tests only
- [ ] `docs` — Documentation only
- [ ] `chore` — Build, deps, CI, tooling

## Changes

<!-- Bullet list of notable changes. Be specific — reviewers read this before the diff. -->

-
-
-

## Testing

<!-- Describe how you tested this. Include test commands, test data used, or manual steps. -->

```bash
make test
```

- [ ] All existing tests pass (`make test`)
- [ ] New tests added for new code
- [ ] Tested manually in local Docker environment

## Screenshots (frontend changes)

<!-- Before / after screenshots for any UI change. Delete this section if backend-only. -->

| Before | After |
|---|---|
| <!-- screenshot --> | <!-- screenshot --> |

## Checklist

### Code quality
- [ ] Linting passes: `cd backend && ruff check .` / `cd frontend && npm run lint`
- [ ] Type checking passes: `cd backend && mypy app/`
- [ ] No secrets, credentials, or PII hardcoded

### Backend (if applicable)
- [ ] New endpoints use appropriate role guard (`require_roles(...)`)
- [ ] Writes to clinical/user data emit audit log entries
- [ ] Pydantic schemas defined for all request/response bodies
- [ ] New dependencies added to correct requirements file with version bounds

### Database (if applicable)
- [ ] Alembic migration created and reviewed
- [ ] `downgrade()` implemented
- [ ] No unsafe column drops or irreversible changes

### Security
- [ ] No new external network calls without review
- [ ] RBAC enforced on new endpoints
- [ ] `.env.example` updated if new env vars were added

### Documentation
- [ ] `CHANGELOG.md` entry added under `[Unreleased]`
- [ ] Docstrings updated for any changed public functions/methods
- [ ] `INSTALL.md` updated if setup steps changed

## Deployment Notes

<!-- Anything the reviewer or deployer needs to know: new env vars required, migration needed before deploy, feature flags, etc. -->

- [ ] Requires database migration before deploy
- [ ] Requires new environment variables (listed below)
- [ ] Requires infrastructure change (Terraform)
- [ ] Safe to deploy without additional steps

<!-- List any new required environment variables: -->
