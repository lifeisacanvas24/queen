12:45 p.m. now brother pull the latest candles from upstox

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

# SSH & GPG Git Setup Guide for macOS

Complete setup for managing multiple GitHub accounts with SSH keys and automated key loading.

---

## 🎯 Quick Start Checklist

- [ ] Generate SSH keys for each account
- [ ] Add keys to ssh-agent and macOS Keychain
- [ ] Add public keys to GitHub
- [ ] Configure `~/.ssh/config`
- [ ] Update Git remotes to use SSH
- [ ] Test connections
- [ ] Setup automation

---

## 🔐 1. SSH Key Setup

### Check Existing Keys

```bash
ls -la ~/.ssh/
# Look for id_ed25519, id_rsa, or custom keys like lifeisacanvas24-github
```

### Add Keys to SSH Agent (Manual)

```bash
ssh-add --apple-use-keychain ~/.ssh/git-zola-admin-access
ssh-add --apple-use-keychain ~/.ssh/git-zola-cms
ssh-add --apple-use-keychain ~/.ssh/lifeisacanvas24-github

# Verify
ssh-add -l
```

### Recommended SSH Config (~/.ssh/config)

```bash
Host github.com-lifeisacanvas24-github
    HostName github.com
    User git
    IdentityFile ~/.ssh/lifeisacanvas24-github
    AddKeysToAgent yes          # Auto-add on first use
    UseKeychain yes             # Store passphrase in Keychain
    IdentitiesOnly yes          # Prevent other keys from being tried

Host github.com-zola-admin
    HostName github.com
    User git
    IdentityFile ~/.ssh/git-zola-admin-access
    AddKeysToAgent yes
    UseKeychain yes
    IdentitiesOnly yes

Host github.com-zola-cms
    HostName github.com
    User git
    IdentityFile ~/.ssh/git-zola-cms
    AddKeysToAgent yes
    UseKeychain yes
    IdentitiesOnly yes
```

### Update Git Remote URLs

```bash
# Check current (likely HTTPS)
git remote -v
# origin  https://github.com/lifeisacanvas24/queen.git

# Change to SSH using config alias
git remote set-url origin git@github.com-lifeisacanvas24-github:lifeisacanvas24/queen.git

# Verify
git remote -v
# origin  git@github.com-lifeisacanvas24-github:lifeisacanvas24/queen.git
```

---

## 🐛 2. Debug SSH Connection Issues

### Test Connection Verbosely

```bash
ssh -vT github.com-lifeisacanvas24-github
```

### Common Problems & Solutions

**❌ Permission denied (publickey)**

```bash
# 1. Check if key is loaded
ssh-add -l

# 2. Copy public key to GitHub
pbcopy < ~/.ssh/lifeisacanvas24-github.pub
# Then paste at: GitHub → Settings → SSH and GPG keys → New SSH key

# 3. Fix file permissions
chmod 600 ~/.ssh/lifeisacanvas24-github
chmod 644 ~/.ssh/lifeisacanvas24-github.pub
chmod 644 ~/.ssh/config

# 4. Test again
ssh -T github.com-lifeisacanvas24-github
# Should show: "Hi lifeisacanvas24! You've successfully authenticated."
```

**❌ Agent has no identities**

```bash
# Add keys manually (see Quick Start)
ssh-add --apple-use-keychain ~/.ssh/lifeisacanvas24-github

# Or fix SSH config to auto-add (see automation section)
```

**❌ Wrong key being used (multiple accounts)**

```bash
# Ensure IdentitiesOnly yes is in SSH config
# This prevents SSH from trying all keys
```

---

## ⚙️ 3. Automate SSH Key Loading

### Method 1: SSH Config Auto-Add (Recommended)

Update `~/.ssh/config` with `AddKeysToAgent yes` as shown above. Keys load automatically on first use.

### Method 2: Shell Startup Script

Add to `~/.zshrc` or `~/.bash_profile`:

```bash
# Add SSH keys on terminal start (suppresses warnings if already loaded)
ssh-add --apple-use-keychain ~/.ssh/git-zola-admin-access 2>/dev/null
ssh-add --apple-use-keychain ~/.ssh/git-zola-cms 2>/dev/null
ssh-add --apple-use-keychain ~/.ssh/lifeisacanvas24-github 2>/dev/null
```

Reload: `source ~/.zshrc`

### Method 3: Persistent Keychain Storage (Best for Scripts)

```bash
# Run ONCE after updating SSH config
ssh-add --apple-use-keychain ~/.ssh/lifeisacanvas24-github

# macOS will remember passphrase across reboots
# No need to re-run unless key changes
```

**For Scheduled Scripts (e.g., 12:45 PM cron jobs):**

- Use Method 1 or 3
- Ensure script runs as your user (not root)
- Or use full path: `/usr/bin/ssh-add --apple-use-keychain /Users/aravindkumar/.ssh/lifeisacanvas24-github`

---

## 🔏 4. GPG Key Setup (For Commit Signing)

### Install GPG

```bash
brew install gnupg
```

### Generate GPG Key

```bash
gpg --full-generate-key
# Select RSA, 4096 bits, 1 year validity
# Enter your GitHub-verified email
```

### Configure Git to Sign Commits

```bash
# Get key ID (after the slash, e.g., 3AA5C34371567BD2)
gpg --list-secret-keys --keyid-format LONG

# Configure Git
git config --global user.signingkey YOUR_KEY_ID
git config --global commit.gpgsign true

# Add public key to GitHub
gpg --armor --export YOUR_KEY_ID | pbcopy
# Paste at: GitHub → Settings → SSH and GPG keys → New GPG key
```

---

## 📋 5. Essential Git Workflow Commands

### File Operations

```bash
# Create file → commit → push
touch new_script.py
git add new_script.py
git commit -m "Add new_script.py — initial version"
git push

# Delete file
rm old_script.py
git add -A
git commit -m "Remove old_script.py (cleanup)"
git push

# Rename file
git mv old_name.py new_name.py
git commit -m "Rename old_name.py → new_name.py"
git push

# Move file to folder
mkdir -p utils
git mv main_script.py utils/main_script.py
git commit -m "Move main_script.py to utils/"
git push

# Delete folder
rm -rf logs/
git add -A
git commit -m "Remove logs/ folder (cleanup)"
git push

# Rename folder
git mv old_folder new_folder
git commit -m "Rename folder old_folder → new_folder"
git push
```

### Daily Workflow

```bash
git checkout main
git pull
# edit files
git add .
git commit -m "Describe what changed"
git push
```

### Undo Commands

```bash
git reset --soft HEAD~1    # Undo commit, keep staged
git reset --mixed HEAD~1   # Undo commit, unstage files
git reset --hard HEAD~1    # Undo commit and DELETE changes
```

### Quick Reference

| Task            | Command                                                     |
| --------------- | ----------------------------------------------------------- |
| Check branch    | `git branch`                                                |
| View changes    | `git status`                                                |
| Stage all       | `git add .`                                                 |
| Commit          | `git commit -m "message"`                                   |
| Push            | `git push`                                                  |
| Pull latest     | `git pull`                                                  |
| Undo edits      | `git restore <file>`                                        |
| Clean untracked | `git clean -fd`                                             |
| New branch      | `git checkout -b feature`                                   |
| Tag release     | `git tag -a v0.1.0 -m "release"` → `git push origin v0.1.0` |

---

## 📌 6. Summary Table

| Action            | Commands                                                                      |
| ----------------- | ----------------------------------------------------------------------------- |
| **Setup SSH**     | Generate keys → Add to agent → Update `~/.ssh/config` → Add pub key to GitHub |
| **Debug SSH**     | `ssh-add -l` → `ssh -vT ALIAS` → Check permissions → Verify GitHub key        |
| **Automate Keys** | Use `AddKeysToAgent yes` in SSH config OR add to `~/.zshrc`                   |
| **Switch to SSH** | `git remote set-url origin git@ALIAS:username/repo.git`                       |
| **Daily Use**     | `git pull` → edit → `git add .` → `git commit` → `git push`                   |

---

## 💡 Pro Tips

- **Commit messages**: Use imperative mood ("Add feature" not "Added feature")
- **SSH aliases**: Use descriptive names like `github.com-work` vs `github.com-personal`
- **Keychain access**: If prompted for passphrase again, re-run with `--apple-use-keychain`
- **Multiple accounts**: `IdentitiesOnly yes` prevents cross-account key leaks

**Every action reversible. Commit often. Stay consistent.**
