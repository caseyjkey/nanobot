# Branching Strategy for Signal Integration

## Current Branch Structure

```
origin/main (795f810)
├── signal-integration-upstream (1b6e9c7) ← CLEAN for upstream PR
│   └── [Signal plan only]
│
└── (25 commits behind)
    └── pr-51 (7e20bf4) ← Base Zhipu PR
        └── coding-plan-support (dd19413) ← Your Z.AI coding plan
            └── signal-integration (7f244f6) ← Personal branch with ALL features
```

## Branch Purposes

### 1. `signal-integration-upstream` (Current branch)
**Purpose**: Clean branch for contributing Signal integration to HKUDS/nanobot

**Contains**:
- Latest upstream main (795f810)
- Signal implementation plan (1b6e9c7)

**Use for**:
- Implementing Signal channel
- Creating PR to upstream
- No dependencies on unmerged features

**Push to**: `fork/signal-integration-upstream` → PR to HKUDS/nanobot

---

### 2. `signal-integration` (Personal branch)
**Purpose**: Your working branch with ALL features

**Contains**:
- Base Zhipu PR (7e20bf4) 
- Z.AI coding plan (dd19413)
- Signal plan (7f244f6)

**Use for**:
- Daily use with your Z.AI coding plan
- Testing Signal with Z.AI models
- Personal deployment

**Push to**: `fork/signal-integration` (optional)

---

### 3. `coding-plan-support`
**Purpose**: Z.AI coding plan feature (waiting for base PR merge)

**Contains**:
- Base Zhipu PR (7e20bf4)
- Z.AI coding plan (dd19413)

**Status**: Ready for PR after base Zhipu PR merges

---

## Recommended Workflow

### For Upstream Contribution (Signal)

```bash
# Work on clean upstream branch
git checkout signal-integration-upstream

# Implement Signal integration (following SIGNAL_PLAN.md)
# ... make changes ...

git add nanobot/channels/signal.py
git commit -m "feat: add Signal channel implementation"

# Push to your fork
git push -u fork signal-integration-upstream

# Create PR: caseyjkey/nanobot:signal-integration-upstream → HKUDS/nanobot:main
```

### For Personal Use (Z.AI + Signal)

Once Signal is implemented on `signal-integration-upstream`:

```bash
# Switch to personal branch
git checkout signal-integration

# Rebase on upstream branch to get Signal implementation
git rebase signal-integration-upstream

# Now you have: Zhipu + Z.AI + Signal
git log --oneline
# 7e20bf4 Zhipu base
# dd19413 Z.AI coding plan
# <Signal commits>
```

---

## Merging Strategy After Upstream Accepts Signal

Scenario: Your Signal PR gets merged to main

```bash
# Update main
git checkout main
git pull origin main

# Your personal branch now needs rebasing
git checkout signal-integration
git rebase main

# Resolve any conflicts (likely none if branches were independent)
# Now your personal branch has: upstream Signal + your Z.AI changes
```

---

## Plan Adjustments for Upstream Contribution

### ✅ No Changes Needed

The `SIGNAL_PLAN.md` is already written for upstream contribution:
- No dependencies on Z.AI coding plan
- Follows existing Telegram/WhatsApp patterns
- Uses standard nanobot config structure
- Clean implementation

### 📝 Optional: Add Contributing Note

If you want to explicitly note this is for upstream:

```markdown
## Contribution Status

**Target**: HKUDS/nanobot upstream
**Branch**: signal-integration-upstream (based on main)
**Dependencies**: None (standalone feature)
```

---

## Testing Strategy

### On `signal-integration-upstream` (upstream PR)
- Test with default models (OpenRouter/Anthropic/OpenAI)
- Ensure no Z.AI-specific code
- Works with fresh `nanobot onboard`

### On `signal-integration` (personal)
- Test with Z.AI GLM-4.7 models
- Test coding plan endpoint routing
- Full integration test

---

## FAQ

**Q: Can I work on both branches simultaneously?**
A: Yes! Use separate terminal sessions or switch with `git checkout`.

**Q: What if base Zhipu PR (7e20bf4) gets merged before Signal PR?**
A: Perfect! Your `coding-plan-support` branch becomes easier to PR, and `signal-integration-upstream` stays clean.

**Q: Should I wait for Z.AI PR to merge before submitting Signal PR?**
A: No! Signal PR is independent. Submit it now on `signal-integration-upstream`.

**Q: How do I keep both branches updated?**
```bash
# Update upstream branch
git checkout signal-integration-upstream
git pull fork signal-integration-upstream
git push fork signal-integration-upstream

# Update personal branch with upstream changes
git checkout signal-integration
git pull --rebase fork signal-integration-upstream
```

---

## Summary

**For upstream contribution**: Use `signal-integration-upstream` (current branch)
**For personal use**: Use `signal-integration` (has Z.AI)
**Keep them in sync**: Rebase personal branch on upstream branch periodically

This strategy gives you:
✅ Clean Signal PR for upstream
✅ Full-featured personal branch
✅ Easy merging when upstream accepts changes
✅ No conflicts between features
