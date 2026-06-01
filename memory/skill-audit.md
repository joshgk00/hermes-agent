# Skill Audit Log

## 2026-05-28 nightly maintenance

- `prompt-optimization-analyzer`: Strong output schema, but trigger scope says “Claude Code skill optimization” while this environment audits Hermes skills too. Suggested rewrite: “Analyze Hermes/Claude Code skill prompts for trigger reliability, token waste, anti-patterns, and publication readiness.” Impact: better trigger accuracy, negligible token change.
- `decision-moment-cards`: Useful but long. Cron delivery rules repeat send/no-send precedence across several bullets. Suggested optimization: merge cron delivery precedence into one ordered rule block. Estimated savings: ~120-180 tokens, clarity moderate.
- `nightly-maintenance-routine`: Good fit for this job. Workflow and git push rules are specific. No critical changes; possible savings ~60 tokens by merging repeated “do not manually deliver” lines.

## 2026-05-29 nightly maintenance

- `prompt-optimization-analyzer`: Still open: description names Claude Code only, but this run audits Hermes skills too. Rewrite description to “Analyze Hermes/Claude Code skill prompts for trigger reliability, token waste, anti-patterns, and publication readiness.” Impact: trigger accuracy better, token change negligible.
- `decision-moment-cards`: Still open: cron delivery precedence repeats across bullets. Merge into one ordered precedence block. Estimated savings: ~120-180 tokens, clarity moderate.
- `nightly-maintenance-routine`: Still open: delivery guidance repeats auto-delivery/no-send handling. Merge workflow step 6 with the cron-specific exception. Estimated savings: ~60 tokens.

## 2026-05-30 nightly maintenance

- `prompt-optimization-analyzer`: Still open: description scopes the role to Claude Code while active use covers Hermes skills. Rewrite description to “Analyze Hermes/Claude Code skill prompts for trigger reliability, token waste, anti-patterns, and publication readiness.” Impact: trigger reliability better, token change negligible.
- `decision-moment-cards`: Still open: cron-specific delivery rules repeat auto-delivery precedence and Matrix send fallback details. Merge into one precedence block plus one fallback block. Estimated savings: ~150-220 tokens, clarity moderate.
- `nightly-maintenance-routine`: Still open: delivery behavior repeats scheduler/no-send precedence. Merge step 6 with pitfalls into one quiet-delivery rule. Estimated savings: ~60 tokens.

## 2026-05-31 nightly maintenance

- `prompt-optimization-analyzer`: Still open: trigger scope says Claude Code, but this run audits Hermes skills. Rewrite description to “Analyze Hermes/Claude Code skill prompts for trigger reliability, token waste, anti-patterns, and publication readiness.” Impact: trigger reliability better, token change negligible.
- `decision-moment-cards`: Still open: cron guidance repeats auto-delivery precedence and manual Matrix fallback. Merge into one precedence block plus one fallback block. Estimated savings: ~150-220 tokens, clarity moderate.
- `nightly-maintenance-routine`: Still open: quiet-delivery/no-send precedence appears in workflow and delivery notes. Merge into one quiet-delivery rule. Estimated savings: ~60 tokens.

## 2026-06-01 nightly maintenance

- `prompt-optimization-analyzer`: Still open: role/description names Claude Code only while active use covers Hermes skills. Rewrite to “Analyze Hermes/Claude Code skill prompts for trigger reliability, token waste, anti-patterns, and publication readiness.” Impact: trigger reliability better, negligible token change.
- `decision-moment-cards`: Still open: Matrix/cron delivery guidance repeats precedence and fallback registration details. Split into one precedence block and one direct-registration fallback block. Estimated savings: ~180-260 tokens, clarity moderate.
- `nightly-maintenance-routine`: Still open: quiet-delivery/no-send rule is repeated in workflow and pitfalls. Merge into one delivery rule. Estimated savings: ~60 tokens.
