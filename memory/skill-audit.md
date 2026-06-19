# Skill Audit Log

## 2026-06-19
- `decision-moment-cards`: Lines 95-127 mix Daily File Review policy, generic cron delivery, and low-level Matrix/Mattermost registration fallbacks. Split platform-registration details into references and keep the main skill to trigger, card shape, and delivery precedence. Estimated savings: ~1,000-1,300 tokens; clarity improvement: significant; trigger reliability: same.
- `prompt-optimization-analyzer`: Lines 47-70 force a full report shape even for cron/internal audits. Add a compact-output mode for audit logs. Estimated savings per use: ~120-250 output tokens; clarity improvement: moderate.
- `nightly-maintenance-routine`: Lines 34-44 and 72-76 correctly resolve cron/no-send precedence, but repeat write-tool and quiet-output rules already present in the job prompt. Keep them because they prevent delivery mistakes; no current rewrite recommended.
