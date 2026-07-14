# Skill Audit

## 2026-07-14

- `decision-moment-cards`: The main prompt embeds platform implementation, troubleshooting, and direct-send recovery details beyond the card-writing trigger. Suggested fix: keep the core pattern and delivery precedence in `SKILL.md`; move adapter design and recovery procedures to linked references. Estimated savings: ~2,500 tokens with better task focus.
- `prompt-optimization-analyzer`: Lines 8-15 use XML role/context wrappers that repeat the description and role. Suggested fix: replace them with one short purpose sentence under the title. Estimated savings: ~45 tokens with no trigger change.
- `nightly-maintenance-routine`: Security and push edge cases dominate the recurring workflow. Suggested fix: keep the workflow and verification list in `SKILL.md`; move detailed triage and push-failure branches into references. Estimated savings: ~500 tokens with clearer nightly execution.