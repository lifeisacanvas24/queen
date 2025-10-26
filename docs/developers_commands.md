# 👑 Queen — Developer Onboarding

Welcome to **Queen**. This guide helps a new contributor go from zero → productive:

- Clone & environment setup
- Project structure and conventions
- Branch, commit, and PR workflow
- Testing & releases (with stable tag mirroring)
- Troubleshooting

---

## 1) Prerequisites

- **Git** (latest)
- **Python 3.12+** (recommended)
- **pip** and optionally **virtualenv** or **venv**
- (Optional) **GitHub CLI** (`gh`) for branch defaults and PRs
- Editor: Zed / VS Code / PyCharm — `.gitignore` already excludes editor metadata

> macOS/iCloud users: We already ignore `.DS_Store` and iCloud sync artifacts.

---

## 2) Clone & Environment

````bash
git clone https://github.com/lifeisacanvas24/queen.git
cd queen

# Create & activate venv
python3 -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows (PowerShell)

# Install dependencies
pip install -r requirements.txt    # if present

If requirements.txt isn’t present yet, install ad-hoc or create one:

pip freeze > requirements.txt


⸻

3) Project Structure (typical)

queen/
├── core/                 # Core orchestration
├── utils/                # Helpers / utilities
├── daemons/              # Background/async services
├── market/               # External integration logic/data
├── configs/              # YAMLs, settings, templates
├── tests/                # Unit/integration tests
└── docs/                 # Docs (Git Bible, onboarding, etc.)

See docs/GIT_COMMANDS.md for common Git tasks.

⸻

4) Configuration & Secrets

Use a local .env (never commit real secrets):

# .env.example
APP_ENV=dev
LOG_LEVEL=INFO
API_KEY=__replace_me__

Developers should copy:

cp .env.example .env
# edit .env as needed (kept out of Git)

If the project uses YAML configs, keep safe defaults in configs/ and load overrides from environment variables when present.

⸻

5) Running & Scripts

Typical run:

python3 main.py

If entrypoints are under modules (e.g., queen/core/app.py), prefer:

python3 -m queen.core.app

Add convenience scripts under scripts/ if needed, e.g.:

scripts/dev_run.sh
scripts/format.sh
scripts/test.sh


⸻

6) Code Style & Tooling
	•	Type hints encouraged; keep functions small and testable.
	•	Black for formatting, ruff or flake8 for linting, mypy for types (optional but recommended).
	•	Pre-commit (optional):

pip install pre-commit
pre-commit install

.pre-commit-config.yaml can include black, ruff, etc.

⸻

7) Branch & Commit Conventions
	•	Base branch: main (kept always green and deployable).
	•	Feature branches: feat/<short-name>
Fix branches: fix/<ticket-or-bug>
Chore/infra: chore/<what>
	•	Commit messages: short imperative summary.
	•	Good: feat: add async fetch for instruments
	•	Good: fix: handle empty payload in parser

Workflow:

git checkout -b feat/some-change
# ...edit...
git add .
git commit -m "feat: some change"
git push -u origin feat/some-change
# open PR → request review → squash/merge into main


⸻

8) Testing

Use pytest:

pip install pytest
pytest -v

Add tests in tests/, name like test_*.py. Keep test data small and local.

⸻

9) Releases (Stable Tag Mirroring)

Queen uses tag-based releases that auto-mirror to a stable repo (lifeisacanvas24/queen-stable) via GitHub Actions.

Release Steps
	1.	Ensure main is green and approved.
	2.	Pick a version (vX.Y.Z) using semantic versioning.
	3.	Tag and push:

git checkout main
git pull
git tag -a v0.1.0 -m "Stable: baseline release"
git push origin v0.1.0

This triggers the Publish Stable workflow:
	•	Pushes the tagged commit to queen-stable’s main
	•	Copies the tag to the stable repo as well

The workflow file lives at .github/workflows/publish-stable.yml.
A repo secret STABLE_PUSH_TOKEN (PAT with repo scope) must be set.

⸻

10) Pull Requests & Reviews
	•	Keep PRs small and focused.
	•	Include a clear description, checklist, and screenshots/logs if relevant.
	•	Request review from maintainers.
	•	Prefer squash & merge to keep main linear and readable.

Branch protection (recommended via GitHub Settings → Branches → Rules):
	•	Require PRs before merging
	•	Require status checks
	•	Disallow force pushes to main

⸻

11) Troubleshooting
	•	Deleted wrong file (not committed): use your editor’s local history or recreate.
	•	Committed something by mistake (not pushed):
	•	Undo last commit, keep changes staged:

git reset --soft HEAD~1


	•	Undo and unstage:

git reset --mixed HEAD~1


	•	Undo and discard changes (dangerous):

git reset --hard HEAD~1


	•	Remote branch confusion:
	•	Confirm:

git branch -a
git remote -v


	•	Set remote HEAD:

git remote set-head origin -a



⸻

12) Contacts
	•	Maintainer: Aravind Kumar (@lifeisacanvas24)
	•	Philosophy: “Code with clarity. Create with awareness.”

May your changes be elegant and your merges effortless. 🌿
EOF

---

## ✅ Commit & Push

```bash
git add docs/DEVELOPER_ONBOARDING.md
git commit -m "docs: add Developer Onboarding guide (clone, setup, PRs, releases)"
git push

That’s it! Your repo now has a complete onboarding playbook for collaborators.
Want me to also drop a tiny RELEASING.md (one-page release checklist + commands) so anyone can confidently cut a stable tag?
````
