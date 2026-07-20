# Skill Audit

## 2026-07-20

- `decision-moment-cards`: Lines 95-136 mix Daily File Review policy and low-level Matrix/Mattermost transport recovery into the core card skill. Suggested fix: move job-specific checks and manual-send recovery into linked references, leaving short routing rules in `SKILL.md`. Estimated savings: ~1,500 tokens.
- `prompt-optimization-analyzer`: Lines 18-22 repeat the frontmatter triggers, while lines 86-113 duplicate report guidance. Suggested fix: remove the activation section and retain one compact example. Estimated savings: ~170 tokens.
- `nightly-maintenance-routine`: Lines 15-19 restate the description, and lines 80-93 repeat delivery and git cautions already stated in the workflow. Suggested fix: delete the class paragraph and merge repeated cautions into their workflow steps. Estimated savings: ~100 tokens.