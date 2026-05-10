# Pre-Push Security Checklist

**IMPORTANT**: Run this checklist before pushing to GitHub to ensure no secrets are exposed.

## Automated Checks

Run these commands to verify repository safety:

### 1. Check Git Status

```bash
git status --short
```

Expected: Only intentionally modified/added files should appear.  
**Warning signs**: `.env`, files in `secrets/`, `*.key`, `*.pem` files

### 2. Check for Secret Files in Git

```bash
# Check for environment files (should only show .env.example)
git ls-files | grep -E '\.env'

# Check for certificate/key files (should be empty)
git ls-files | grep -E '\.(key|pem|crt|p12|pfx|cer|der)$'

# Check for secrets directory (should be empty)
git ls-files | grep secrets/
```

**Expected result**: Only `.env.example` and `.env.connectathon.example` should be tracked, nothing else.

### 3. Verify Gitignore is Working

```bash
# These should all return "Ignored" or not found
git check-ignore .env
git check-ignore secrets/
git check-ignore node_modules/
git check-ignore dist/
```

### 4. Search for Accidentally Committed Secrets

```bash
# Search for common secret patterns in tracked files
git grep -i 'private[_-]key' -- ':!*.example' ':!docs/' ':!*.md'
git grep -i 'secret' -- ':!*.example' ':!docs/' ':!*.md' ':!package*.json'
git grep -E '[A-Za-z0-9+/]{32,}' -- '*.env' 2>/dev/null
```

**Expected result**: No matches (or only false positives in documentation)

### 5. Build and Test

```bash
# Verify project builds and tests pass
npm run build
npm test
```

**Expected result**: All tests pass, clean build with no errors

### 6. Verify Mock Flow Works

```bash
# Start server in background
npm start &
SERVER_PID=$!
sleep 5

# Test endpoints
curl -s http://localhost:3009/health | grep '"status":"ok"'
npm run adapter:e2e:check

# Stop server
kill $SERVER_PID
```

**Expected result**: All checks pass

## Manual Verification

### Check Recently Added Files

```bash
# List files added in last commit
git diff --name-only HEAD~1

# Review content of each new file
git show HEAD:<filename>
```

**Review for**:
- Hardcoded passwords or tokens
- Real certificate content
- Personal identifiable information (PII)
- Internal URLs or hostnames
- API keys or secrets

### Check Modified Files

```bash
# Show all changes in staged files
git diff --cached
```

**Look for**:
- Accidentally committed debugging code that prints secrets
- Hardcoded test tokens
- Real configuration values
- Comments with sensitive information

### Verify .env Files

```bash
# Ensure .env is not tracked
ls -la .env 2>/dev/null && echo "⚠️  WARNING: .env file exists" || echo "✓ No .env file"
git ls-files .env 2>/dev/null && echo "❌ DANGER: .env is tracked!" || echo "✓ .env not tracked"

# Check .env.example contains no secrets
cat .env.example | grep -E '(private|secret|password|token)' | grep -v '#' | grep -v 'PATH=' | grep -v 'MODE='
```

**Expected**: Should only see placeholder values, no real secrets

## If You Find Tracked Secrets

### Remove from Staging

```bash
# Unstage a file
git reset HEAD <filename>

# Or unstage all
git reset HEAD
```

### Remove from Git History (if already committed)

```bash
# Remove from last commit (not pushed yet)
git rm --cached <filename>
git commit --amend

# If already pushed - DO NOT PUSH MORE
# Contact team lead immediately
# May need to rotate secrets and rewrite history
```

### For Committed Secrets Already Pushed

1. **STOP** - Do not push more commits
2. **Rotate the exposed secret immediately**
3. **Contact security team**
4. **Consider repository as compromised**
5. **May need BFG Repo-Cleaner or git-filter-repo**

## Checklist Summary

- [ ] `git status` shows only intended files
- [ ] No `.env` files tracked (except examples)
- [ ] No `secrets/` directory tracked
- [ ] No `*.key`, `*.pem`, `*.crt` files tracked
- [ ] `.gitignore` is working correctly
- [ ] No secret patterns found in tracked files
- [ ] `npm run build` succeeds
- [ ] `npm test` passes (all tests)
- [ ] Mock flow works (`npm run adapter:e2e:check`)
- [ ] Manually reviewed new/modified files
- [ ] No hardcoded secrets in code
- [ ] `.env.example` contains only placeholders

## After Push

### Verify on GitHub

1. Browse repository on GitHub
2. Check recent commits
3. Verify no secrets visible
4. Check "Code" search for sensitive patterns

### If You Discover a Pushed Secret

**Immediate Actions:**

1. Rotate/revoke the exposed secret
2. Notify security team
3. File incident report
4. Remove from history using BFG or git-filter-repo
5. Force push cleaned history (coordinate with team)
6. Audit for any unauthorized access

## Additional Resources

- [GitHub: Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)
- [git-filter-repo](https://github.com/newren/git-filter-repo)

## Questions?

Contact the security team before pushing if uncertain about any file.
