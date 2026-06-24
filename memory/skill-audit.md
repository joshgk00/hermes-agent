# Skill Audit Log

## 2026-06-22
- `decision-moment-cards`: Lines 107-126 over-specify Matrix/Mattermost cron delivery fallback details inside the main skill. Suggested fix: move direct-send registration edge cases to `references/direct-matrix-card-registration.md` and keep only the decision-card shape plus delivery precedence in SKILL.md. Estimated savings/impact: ~700 tokens and better trigger-time focus.
- `prompt-optimization-analyzer`: Lines 84-110 use two XML-wrapped examples after the format contract is already clear. Suggested fix: keep one compact example and move the second to references or delete it. Estimated savings/impact: ~150 tokens.
- `nightly-maintenance-routine`: Lines 46-58 repeat detailed security-scan triage that already belongs in linked references. Suggested fix: keep scanner scope and escalation rules in SKILL.md, move examples to `references/security-scan-triage.md`. Estimated savings/impact: ~250 tokens.

## 2026-06-23
- `decision-moment-cards`: Prior line 4 issue still open; main SKILL.md is ~4,227 tokens, with direct Matrix/Mattermost fallback details dominating trigger-time context. Suggested fix: move registration/runbook details to references and keep delivery precedence plus card schema in SKILL.md. Estimated savings/impact: ~700 tokens and better mobile-decision reliability.
- `prompt-optimization-analyzer`: Prior line 5 issue still open; examples duplicate the report contract. Suggested fix: keep one compact before/after example and delete or move the second. Estimated savings/impact: ~150 tokens.
- `nightly-maintenance-routine`: Prior line 6 issue still open; security examples duplicate linked triage references. Suggested fix: keep escalation rules in SKILL.md and move detailed examples to `references/security-scan-triage.md`. Estimated savings/impact: ~250 tokens.

## 2026-06-24 Nightly Maintenance
- `decision-moment-cards`: Lines 53-113 and 129-149 repeat Matrix delivery and direct-registration guidance across cron branches. Suggested fix: move the fallback send/register procedure to one reference and keep only the precedence rule plus required card format in SKILL.md. Estimated savings/impact: ~450 tokens and lower conflict risk.
- `decision-moment-cards`: Lines 6-14 define the compact card contract, but later cron guidance adds many transport-specific exceptions. Suggested fix: split "card content" from "delivery plumbing" sections and keep cron no-send precedence near the top. Estimated savings/impact: trigger/action clarity improvement.
- `prompt-optimization-analyzer`: Lines 39-62 require detailed line/token reporting for every issue; the compact audit format already covers maintenance jobs. Suggested fix: state that cron audits should report only changed/new findings unless publication review is requested. Estimated savings/impact: ~80 tokens per recurring run.
