# 🚀 Releasing — Queen

This is the one-page checklist to cut a stable release from `main`.
Releases are versioned as **tags** (`vX.Y.Z`) and mirrored to **queen-stable** via CI.

---

## ✅ Preconditions (do once per release)

- You’re on `main`, up to date:

  ```bash
  git checkout main
  git pull

  •	Tests pass locally:
  ```

pytest -v

    •	Optional: bump version in code/configs if you keep one (e.g., __version__).

⸻

🧮 Versioning Guideline
• MAJOR: breaking changes → v2.0.0
• MINOR: backward-compatible features → v1.1.0
• PATCH: fixes, small changes → v1.0.1

Pick the next tag carefully before proceeding.

⸻

🏷️ Create & Push the Release Tag

Replace v0.1.0 with your version.

git checkout main
git pull
git tag -a v0.1.0 -m "Stable: short description of changes"
git push origin v0.1.0

What happens next:
• GitHub Actions in queen runs Publish Stable workflow
• The exact tagged commit is pushed to queen-stable’s main
• The tag is copied to queen-stable too

⸻

🔎 Verify the Release
• Actions tab (in lifeisacanvas24/queen) → workflow Publish Stable is green
• Visit lifeisacanvas24/queen-stable → branch main updated to the tagged commit
• (Optional) Check the tag exists in the stable repo as well

⸻

📝 Draft Release Notes (optional)

Create a GitHub Release from the tag and include:
• Highlights
• Breaking changes (if any)
• Upgrade notes
• Thanks / credits

⸻

♻️ Hotfix After a Release 1. Create a fix on main, test, and commit 2. Cut a new patch tag:

git checkout main
git pull
git tag -a v0.1.1 -m "Stable: hotfix for <issue>"
git push origin v0.1.1

⸻

⏪ Rollback (emergency) 1. Identify the previous good tag (e.g., v0.1.0) 2. Re-tag to a new patch pointing at that commit (do not delete history):

# find commit of the good tag

git rev-list -n 1 v0.1.0

# suppose it prints ABCDEF...

git tag -a v0.1.2 ABCDEF -m "Stable: rollback to v0.1.0 commit"
git push origin v0.1.2

CI will mirror that commit to queen-stable.

⸻

🧰 Useful Commands

# list tags

git tag --list

# show tag details

git show v0.1.0

# delete a local tag (careful)

git tag -d v0.1.0

# delete a remote tag (careful)

git push origin :refs/tags/v0.1.0

⸻

🔐 CI Prereq (already set up)
• Workflow: .github/workflows/publish-stable.yml
• Secret: STABLE_PUSH_TOKEN (PAT with repo scope)

⸻

Keep main green, tag with care, and let CI mirror it to queen-stable.
EOF

### ✅ Commit & push it

```bash
git add docs/RELEASING.md
git commit -m "docs: add RELEASING guide (tag flow + stable mirroring)"
git push
```
