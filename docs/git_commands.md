11:45 a.m. now brother pull the latest candles from upstox

## ⚙️ 1️⃣ Create a Local File → Commit → Push to GitHub

````bash
touch new_script.py
git add new_script.py
git commit -m "Add new_script.py — initial version"
git push

✅ File now exists locally and on GitHub.

⸻

🗑️ 2️⃣ Delete a Local File and Remove It from GitHub

rm old_script.py
git add -A
git commit -m "Remove old_script.py (cleanup)"
git push

✅ File is deleted from both your machine and GitHub.

⸻

🧾 3️⃣ Rename a File and Update GitHub

git mv old_name.py new_name.py
git commit -m "Rename old_name.py → new_name.py"
git push

✅ GitHub automatically reflects the rename.

⸻

📦 4️⃣ Move a File Between Directories

mkdir -p utils
git mv main_script.py utils/main_script.py
git commit -m "Move main_script.py to utils/"
git push

✅ File is moved locally and remotely with full history preserved.

⸻

📁 5️⃣ Delete or Rename a Folder

🧹 Delete Folder

rm -rf logs/
git add -A
git commit -m "Remove logs/ folder (cleanup)"
git push

✏️ Rename Folder

git mv old_folder new_folder
git commit -m "Rename folder old_folder → new_folder"
git push

✅ Git tracks folder-level changes perfectly.

⸻

🧠 Extra Good-to-Know Commands

Task	Command	Description
Check current branch	git branch	Shows current working branch
View unstaged changes	git status	See modified or untracked files
Stage all changes	git add .	Adds all new/changed files
Commit changes	git commit -m "message"	Saves snapshot with a message
Push to GitHub	git push	Uploads commits to GitHub
Pull latest from GitHub	git pull	Syncs local branch with remote
Undo unstaged file edits	git restore <file>	Restores file before commit
Remove untracked files	git clean -fd	Deletes ignored/untracked files
New branch	git checkout -b feature	Creates and switches to branch


⸻

🧩 6️⃣ Typical Daily Workflow

git checkout main
git pull
# edit files
git add .
git commit -m "Describe what changed"
git push

✅ Safe, standard daily update sequence.

⸻

⚡ 7️⃣ Undo or Revert a Commit (Careful)

git reset --soft HEAD~1    # undo commit, keep staged
git reset --mixed HEAD~1   # undo commit, unstage files
git reset --hard HEAD~1    # undo commit and delete changes


⸻

🌿 8️⃣ Tagging and Releasing (For Stable Pipeline)

git tag -a v0.1.0 -m "Stable baseline release"
git push origin v0.1.0

✅ Triggers the auto-mirror workflow to queen-stable.

⸻

🪶 Quick Reference Table

Action	Command Summary
Create file → push	touch → git add → git commit → git push
Delete file	rm → git add -A → git commit → git push
Rename file/folder	git mv → git commit → git push
Move file	git mv old_path new_path → git commit → git push
Tag release	git tag -a vX.Y.Z -m "msg" → git push origin vX.Y.Z


⸻

🪷 Remember: Commit often, write clear messages, and keep main pristine.
Every action in Git is reversible — clarity and consistency make you unstoppable.
EOF

---

### ✅ Then commit & push it
```bash
git add docs/GIT_COMMANDS.md
git commit -m "Add GIT_COMMANDS.md — Queen Git Bible"
git push
````
