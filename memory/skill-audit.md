# Skill Audit Log

## 2026-06-22
- `decision-moment-cards`: Lines 107-126 over-specify Matrix/Mattermost cron delivery fallback details inside the main skill. Suggested fix: move direct-send registration edge cases to `references/direct-matrix-card-registration.md` and keep only the decision-card shape plus delivery precedence in SKILL.md. Estimated savings/impact: ~700 tokens and better trigger-time focus.
- `prompt-optimization-analyzer`: Lines 84-110 use two XML-wrapped examples after the format contract is already clear. Suggested fix: keep one compact example and move the second to references or delete it. Estimated savings/impact: ~150 tokens.
- `nightly-maintenance-routine`: Lines 46-58 repeat detailed security-scan triage that already belongs in linked references. Suggested fix: keep scanner scope and escalation rules in SKILL.md, move examples to `references/security-scan-triage.md`. Estimated savings/impact: ~250 tokens.
