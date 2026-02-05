# Z.AI Coding Plan Support

Extends PR #51 to add Z.AI's Coding Plan endpoint. Adds `coding_plan: bool` config field that routes requests to `https://api.z.ai/api/coding/paas/v4` when enabled. Onboarding now prompts users to select between Coding Plan (glm-4.7, glm-4.7-flash only) or General Plan. No vLLM modifications needed—works with base PR #51 changes.

## Testing Checklist

- [ ] Run `python /tmp/test_coding_plan.py` — verify 4 checks pass
- [ ] Run `nanobot onboard` — select Zhipu AI → Coding Plan → enter API key
- [ ] Verify config has `coding_plan: true` and `zai/glm-4.7` model
- [ ] Test request: `nanobot agent -m "Write a Python function"`
- [ ] Set `coding_plan: false` and verify general plan still works
