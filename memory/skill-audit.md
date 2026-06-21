# Skill Audit Log

## 2026-06-19
- `decision-moment-cards`: Lines 95-127 mix Daily File Review policy, generic cron delivery, and low-level Matrix/Mattermost registration fallbacks. Split platform-registration details into references and keep the main skill to trigger, card shape, and delivery precedence. Estimated savings: ~1,000-1,300 tokens; clarity improvement: significant; trigger reliability: same.
- `prompt-optimization-analyzer`: Lines 47-70 force a full report shape even for cron/internal audits. Add a compact-output mode for audit logs. Estimated savings per use: ~120-250 output tokens; clarity improvement: moderate.
- `nightly-maintenance-routine`: Lines 34-44 and 72-76 correctly resolve cron/no-send precedence, but repeat write-tool and quiet-output rules already present in the job prompt. Keep them because they prevent delivery mistakes; no current rewrite recommended.

## 2026-06-20
- `decision-moment-cards`: Still open: lines 95-127 pack Daily File Review policy, cron delivery precedence, Matrix/Mattermost internals, and manual registration fallbacks into the main skill. Suggested fix: move low-level platform registration into references and keep the main skill focused on card shape, delivery precedence, and duplicate suppression. Estimated savings/impact: ~1,000-1,300 tokens; significant clarity improvement.
- `prompt-optimization-analyzer`: Low issue: full report format remains over-specified for cron audits. Suggested fix: make compact audit output the default when caller context is cron/internal. Estimated savings/impact: ~120-250 output tokens per run; moderate clarity improvement.

## 2026-06-21
- `decision-moment-cards`: Still open: the main skill includes detailed Matrix/Mattermost implementation and cron edge cases that belong in references. Suggested fix: keep only card shape, delivery precedence, and duplicate suppression in `SKILL.md`. Estimated savings/impact: ~1,000-1,300 tokens; significant clarity improvement.
- `prompt-optimization-analyzer`: Low issue: the skill still emphasizes full report output before compact audit output. Suggested fix: make cron/internal compact entries the default path. Estimated savings/impact: ~120-250 output tokens per run; moderate clarity improvement.
