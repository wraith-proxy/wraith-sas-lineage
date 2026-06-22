# 👻 Ghost Stack Pull Request

## 🎯 Purpose
_What are we haunting today? Briefly describe the change._

**Fixes:** # (Link the Gitea Issue here)

---

## 🛠️ Proposed Changes
- [ ] Logic updated in `src/`
- [ ] Dependencies synced via `uv lock`
- [ ] Schema updated in `schema/` if models changed

---

## 🚦 Quality Gate (The Ghost Protocol)
- [ ] **uv Sync:** Environment is healthy and `uv.lock` is up to date.
- [ ] **Tests:** `./bin/run_tests.sh` passes with >80% coverage.
- [ ] **Linting:** `pre-commit run --all-files` passes.
- [ ] **Commits:** Messages follow the `cz_customize` regex (Fix/Feature/Break).

---

## 🧪 Deployment & Verification
- [ ] Branch is synced with the latest `main`.
- [ ] Thin-slice test (one job end-to-end) passes if parser heuristics changed.

---

## 👤 Author's Final Word
_Any specific notes for the reviewer or warnings about breaking changes?_
