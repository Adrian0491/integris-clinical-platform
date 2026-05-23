# Contributing to Integris Clinical Platform

Thank you for contributing to the Integris Clinical Platform. This document covers coding standards, branch strategy, and the pull request process.

> **Security issues**: Do **not** open a public issue. Follow the process in [SECURITY.md](SECURITY.md).

---

## Table of Contents

- [Development Setup](#development-setup)
- [Branch Strategy](#branch-strategy)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Backend Standards](#backend-standards)
- [Frontend Standards](#frontend-standards)
- [Testing Requirements](#testing-requirements)
- [Database Migrations](#database-migrations)
- [Code Review Checklist](#code-review-checklist)

---

## Development Setup

Follow [INSTALL.md](INSTALL.md) to get a fully working local environment before making any changes.

---

## Branch Strategy

We use a **trunk-based development** model with three long-lived branches:

| Branch | Purpose | Protection |
|---|---|---|
| `main` | Production-ready code | Requires PR + 1 approval + passing CI |
| `staging` | Pre-production integration | Requires PR + passing CI |
| `dev` | Shared development integration | Requires PR |

### Short-lived branch naming

Create feature and fix branches off `main`. Use the following prefixes:

| Prefix | When to use | Example |
|---|---|---|
| `feature/` | New functionality | `feature/findings-export-csv` |
| `fix/` | Bug fixes | `fix/refresh-token-expiry` |
| `hotfix/` | Critical prod fixes | `hotfix/auth-bypass-cve-2026-001` |
| `chore/` | Tooling, deps, CI | `chore/bump-angular-21.2` |
| `docs/` | Documentation only | `docs/update-install-guide` |

Branch names must be lowercase and hyphen-separated. No underscores, no uppercase.

### Never push directly to `main` or `staging`

All changes go through pull requests. Force-pushes to `main` are blocked by branch protection rules.

---

## Commit Messages

Follow the **Conventional Commits** specification (https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer: BREAKING CHANGE, Closes #123]
```

### Types

| Type | When to use |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `perf` | Performance improvement |
| `refactor` | Code change without behavior change |
| `test` | Adding or fixing tests |
| `docs` | Documentation only |
| `chore` | Build, deps, CI, tooling |
| `revert` | Reverts a previous commit |

### Scopes

`auth`, `studies`, `datasets`, `validation`, `findings`, `reports`, `audit`, `infra`, `frontend`, `api`, `worker`, `db`

### Examples

```
feat(findings): add CSV export for resolved findings

fix(auth): prevent refresh token reuse after logout

chore(deps): bump FastAPI to 0.115.4

test(validation): add edge cases for empty domain files

docs(install): clarify Elasticsearch vm.max_map_count step
```

### Rules

- Summary line: imperative mood, no period, ≤ 72 characters
- Body: wrap at 100 characters; explain *why*, not *what*
- Reference issues: `Closes #42` or `Refs #17`

---

## Pull Request Process

### Before opening a PR

- [ ] All tests pass locally: `make test`
- [ ] Linting passes: `cd backend && ruff check .` / `cd frontend && npm run lint`
- [ ] Type checks pass: `cd backend && mypy app/`
- [ ] New code has corresponding tests (see [Testing Requirements](#testing-requirements))
- [ ] Migrations are reviewed (no data loss, no irreversible changes)
- [ ] `.env.example` updated if new environment variables were added

### PR size

Keep PRs focused. A PR that changes 800+ lines across unrelated areas will be asked to split. Prefer:
- One logical change per PR
- Separate refactoring PRs from feature PRs
- Separate migration PRs from application logic PRs

### PR title

Use the same Conventional Commits format as your commit messages:
```
feat(reports): add PDF watermarking for draft reports
```

### Review requirements

| Target branch | Approvals required | CI required |
|---|---|---|
| `main` | 1 | ✅ all checks green |
| `staging` | 1 | ✅ all checks green |
| `dev` | 0 | ✅ lint + test |

### Merging

- Use **Squash and merge** for feature branches (keeps `main` history clean)
- Use **Merge commit** for `staging → main` promotions
- Delete the source branch after merging

---

## Backend Standards

**Language**: Python 3.12+  
**Linter / formatter**: `ruff` (replaces flake8, isort, black)  
**Type checker**: `mypy`

### Code style

```bash
# Format and lint
cd backend
ruff format .
ruff check --fix .

# Type check
mypy app/
```

`ruff` and `mypy` are enforced in CI. PRs that fail either check will not be merged.

### Key conventions

- All route handlers in `app/api/v1/` — one file per resource
- Business logic lives in `app/services/` — route handlers must not query the database directly
- SQLAlchemy ORM only (no raw SQL except in migrations)
- All database writes that modify user or clinical data must emit an audit log entry via `app.core.audit`
- Pydantic schemas for all request bodies and responses — no naked `dict` returns from endpoints
- `Optional[X]` written as `X | None` (Python 3.10+ union syntax)
- `from __future__ import annotations` in every module

### Dependency management

- **Production** deps go in `backend/requirements.txt` with `>=X.Y,<Z.0` ranges
- **Dev / test** deps go in `backend/requirements-dev.txt`
- Do not add dev-only packages to the production requirements file

---

## Frontend Standards

**Framework**: Angular 21 (standalone components, signals)  
**UI library**: Angular Material 3  
**Language**: TypeScript 5.9 (strict mode)

### Code style

```bash
cd frontend
npm run lint    # ng lint
```

### Key conventions

- All components are **standalone** — no `NgModule` declarations
- Use `inject()` instead of constructor injection
- Use **signals** (`signal()`, `computed()`, `effect()`) for local reactive state
- Use `@if` / `@for` control flow syntax (not `*ngIf` / `*ngFor` directives)
- Services in `app/core/services/` extend `ApiService` which sets the base URL and auth headers
- Never call `HttpClient` directly from a component — always go through a typed service
- Keep templates free of business logic: derive computed values in the component class
- CSS: scoped component styles only, no global styles except `styles.scss` theme variables

### Component file conventions

| File | Contains |
|---|---|
| `feature-name.ts` | `@Component` class |
| `feature-name.html` | Template |
| `feature-name.css` | Component-scoped styles |

Simple components (dialogs, small widgets) may use inline `template` and `styles` arrays.

---

## Testing Requirements

### Backend

Tests live in `backend/tests/` and run against a real PostgreSQL database (`cdtool_test`).

| What changed | Tests required |
|---|---|
| New endpoint | Integration test covering happy path + at least one auth/permission failure |
| New service method | Unit or integration test covering logic branches |
| New validation rule | Test with a dataset that triggers the rule + one that does not |
| Bug fix | Regression test that would have caught the bug |

**Minimum coverage target**: 80% for new code introduced in a PR.

```bash
make test                            # full suite
make test-fast                       # stop on first failure
cd backend && pytest tests/ --cov=app --cov-report=term-missing
```

### Frontend

Run Angular tests with:

```bash
cd frontend
npm test
```

Component tests are required for any component that contains non-trivial logic (form validation, signal derivations, conditional rendering).

---

## Database Migrations

Every schema change must be accompanied by an Alembic migration.

```bash
# After modifying a SQLAlchemy model:
make makemigration msg="add signed_at column to reports"
```

**Migration review checklist**:

- [ ] `upgrade()` and `downgrade()` are both implemented
- [ ] No `DROP COLUMN` or `DROP TABLE` without a deprecation period
- [ ] Large table alterations (adding NOT NULL columns to tables > 100k rows) use a multi-step migration: add nullable → backfill → add NOT NULL constraint
- [ ] Migration is idempotent when possible (use `IF NOT EXISTS`)
- [ ] Migration file has a clear `"""docstring"""` describing the change

---

## Code Review Checklist

Reviewers should verify:

- [ ] Logic is correct and handles edge cases
- [ ] No secrets, credentials, or PII hardcoded
- [ ] Audit logging added for any action that writes clinical or user data
- [ ] RBAC enforced — new endpoints use appropriate role guards
- [ ] Error responses use consistent format (`{"detail": "..."}`)
- [ ] No new external network calls without review (supply chain / data egress risk)
- [ ] Dependencies added to the correct requirements file with version bounds

---

## Questions

Open a GitHub Discussion or reach out to the engineering team at **engineering@integris-clinical.com**.

© 2026 Integris Clinical Services LLC
