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

## 2026-06-25 Nightly Maintenance
- `decision-moment-cards`: Lines 115-149 duplicate delivery precedence and direct-send recovery cases already covered by the cron-specific bullets. Suggested fix: keep the no-send precedence plus card schema in SKILL.md and move Matrix/Mattermost implementation notes to references. Estimated savings/impact: ~500 tokens and fewer delivery conflicts.
- `nightly-maintenance-routine`: Lines 65-82 include detailed secret-scan examples while linked triage references exist. Suggested fix: keep critical/benign classification rules in SKILL.md and move concrete examples to `references/security-scan-triage.md`. Estimated savings/impact: ~200 tokens.

## 2026-06-26 Nightly Maintenance
- `decision-moment-cards`: Prior Matrix/Mattermost delivery-plumbing issue still open; the loaded skill spends most cron guidance on transport fallback details. Suggested fix: move fallback send/register procedures to linked references and keep only card format plus delivery precedence in SKILL.md. Estimated savings/impact: ~500-700 tokens and fewer auto-delivery conflicts.
- `prompt-optimization-analyzer`: Lines 84-110 still carry two examples after the audit format is specified. Suggested fix: keep one compact example and move the second to references or delete it. Estimated savings/impact: ~150 tokens.
- `nightly-maintenance-routine`: Security-scan section still embeds detailed benign-match examples despite linked triage references. Suggested fix: keep escalation criteria in SKILL.md and move examples to `references/security-scan-triage.md`. Estimated savings/impact: ~200 tokens.

## 2026-06-27 Nightly Maintenance
- `decision-moment-cards`: Prior Matrix/Mattermost delivery-plumbing issue still open; current loaded skill still embeds long direct-send/register fallback rules and conflicting cron delivery branches. Suggested fix: split platform fallback procedures into references and keep SKILL.md to trigger, card schema, and delivery precedence. Estimated savings/impact: ~1,200-1,800 tokens and clearer cron behavior.
- `prompt-optimization-analyzer`: XML wrapper sections repeat the description and role before the rubric. Suggested fix: fold `<context>` and `<role>` into one short purpose paragraph. Estimated savings/impact: ~80-120 tokens with same trigger reliability.
- `nightly-maintenance-routine`: Security-scan guidance still duplicates detailed regex triage that is already in linked references. Suggested fix: keep the high-level workflow in SKILL.md and move pattern examples to `references/security-scan-triage.md`. Estimated savings/impact: ~250-400 tokens.

## 2026-06-28 Nightly Maintenance
- `decision-moment-cards`: Prior delivery-plumbing issue still open; loaded skill still mixes card schema with long Matrix/Mattermost fallback implementation notes. Suggested fix: move send/register recovery details to references and keep SKILL.md to trigger, card fields, and delivery precedence. Estimated savings/impact: ~1,200 tokens and fewer cron delivery conflicts.
- `prompt-optimization-analyzer`: Prior XML/context duplication issue still open. Suggested fix: replace `<context>` plus `<role>` with one short purpose paragraph before the rubric. Estimated savings/impact: ~80-120 tokens.
- `nightly-maintenance-routine`: Prior detailed security-scan examples still open despite linked references. Suggested fix: keep only scan scope, escalation criteria, and reference links in SKILL.md. Estimated savings/impact: ~250-400 tokens.

## 2026-06-29 Nightly Maintenance
- `decision-moment-cards`: Prior delivery-plumbing issue still open; cron guidance still embeds direct Matrix/Mattermost fallback implementation details in the trigger-time skill. Suggested fix: move send/register runbooks to references and keep only card schema plus delivery precedence in SKILL.md. Estimated savings/impact: ~1,200 tokens and fewer no-send conflicts.
- `prompt-optimization-analyzer`: Prior XML/context duplication issue still open. Suggested fix: merge `<context>` and `<role>` into a single purpose sentence before the rubric. Estimated savings/impact: ~80-120 tokens.
- `nightly-maintenance-routine`: Prior detailed secret-scan triage issue still open. Suggested fix: keep scan scope and escalation rules in SKILL.md; move pattern examples to linked references. Estimated savings/impact: ~250-400 tokens.

## 2026-07-04 Nightly Maintenance
- `decision-moment-cards`: Prior delivery-plumbing issue still open; loaded skill still includes long Matrix/Mattermost direct-send and manual-registration runbooks. Suggested fix: keep delivery precedence and card schema in SKILL.md; move send/register recovery details to references. Estimated savings/impact: ~1,200 tokens and lower cron conflict risk.
- `prompt-optimization-analyzer`: Prior XML/context duplication issue still open. Suggested fix: merge `<context>` and `<role>` into one purpose sentence before the rubric. Estimated savings/impact: ~80-120 tokens.
- `nightly-maintenance-routine`: Prior secret-scan triage duplication still open. Suggested fix: keep scope, escalation rules, and reference links in SKILL.md; move concrete benign-match examples to linked references. Estimated savings/impact: ~250-400 tokens.

## 2026-07-06 Nightly Maintenance
- `decision-moment-cards`: Prior delivery-plumbing issue still open; loaded skill still carries direct Matrix/Mattermost send and registration runbooks in trigger-time context. Suggested fix: keep card schema and no-send precedence in SKILL.md; move fallback transport procedures to references. Estimated savings/impact: ~1,200 tokens and lower cron conflict risk.
- `prompt-optimization-analyzer`: Prior XML/context duplication issue still open. Suggested fix: merge `<context>` and `<role>` into one purpose sentence before the rubric. Estimated savings/impact: ~80-120 tokens.
- `nightly-maintenance-routine`: Prior secret-scan triage duplication still open; detailed benign-match examples duplicate linked references. Suggested fix: keep scan scope and escalation criteria in SKILL.md; move example lists to references. Estimated savings/impact: ~250-400 tokens.

## 2026-07-08 Nightly Maintenance
- `decision-moment-cards`: Prior delivery-plumbing issue still open; current loaded skill still embeds long Matrix/Mattermost send, recovery, and registration procedures in trigger-time context. Suggested fix: keep card schema plus auto-delivery precedence in SKILL.md and move fallback transport runbooks to references. Estimated savings/impact: ~1,200 tokens and lower cron conflict risk.
- `prompt-optimization-analyzer`: Prior XML/context duplication issue still open. Suggested fix: merge `<context>` and `<role>` into one purpose sentence before the rubric. Estimated savings/impact: ~80-120 tokens.
- `nightly-maintenance-routine`: Prior secret-scan triage duplication still open; detailed benign examples duplicate linked references. Suggested fix: keep scan scope and escalation criteria in SKILL.md; move example lists to references. Estimated savings/impact: ~250-400 tokens.

## 2026-07-09 Nightly Maintenance
- `decision-moment-cards`: Prior delivery-plumbing issue still open; loaded skill still mixes card schema with Matrix/Mattermost send, recovery, and manual registration runbooks. Suggested fix: move fallback transport procedures to references and keep only card fields plus delivery precedence in SKILL.md. Estimated savings/impact: ~1,200 tokens and lower no-send conflict risk.
- `prompt-optimization-analyzer`: Prior XML/context duplication issue still open. Suggested fix: merge `<context>` and `<role>` into one purpose sentence before the rubric. Estimated savings/impact: ~80-120 tokens.
- `nightly-maintenance-routine`: Prior secret-scan triage duplication still open; detailed benign examples duplicate linked references. Suggested fix: keep scan scope and escalation criteria in SKILL.md; move example lists to references. Estimated savings/impact: ~250-400 tokens.

## 2026-07-10 Nightly Maintenance
- `decision-moment-cards`: Prior delivery-plumbing issue still open; current loaded skill still embeds direct Matrix/Mattermost send, recovery, and manual-registration runbooks despite linked references. Suggested fix: keep only card schema, no-send precedence, and fallback command requirements in SKILL.md. Estimated savings/impact: ~1,200 tokens and lower cron delivery conflict risk.
- `prompt-optimization-analyzer`: Prior XML/context duplication issue still open. Suggested fix: merge `<context>` and `<role>` into one purpose sentence before the rubric. Estimated savings/impact: ~80-120 tokens.
- `nightly-maintenance-routine`: Prior secret-scan triage duplication still open; detailed benign examples duplicate linked references. Suggested fix: keep scan scope and escalation criteria in SKILL.md; move example lists to references. Estimated savings/impact: ~250-400 tokens.
