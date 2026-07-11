# Human Baseline Protocol

Status: specified for future benchmark cycles. Cycle 1 does not include a human-baseline arm; see [cycle-1-release-notes.md](cycle-1-release-notes.md).

## Purpose

The human baseline estimates how calibrated legal forecasters perform on the same frozen pre-decision packets shown to models. It is a construct-validity comparison, not a replacement for the model leaderboard, and it must be reported only for units where the human and model saw the same packet version.

## Recruitment

Recruit reviewers into the existing expertise strata: `law_student`, `junior_litigator`, `midlevel_litigator`, `senior_litigator`, and `expert_panel`. A cycle that reports a headline human arm must recruit at least two reviewers in each reported expertise stratum and must disclose any stratum that is omitted. Project authors, benchmark maintainers, model submitters, and anyone who saw outcome labels for the sampled units are excluded from forecasting. Reviewers consent in writing to research use of their anonymized forecasts, ratings, timing, and notes before forecasting begins.

## Sample Size By Stratum

The minimum reportable design is 25 shared prediction units per complexity stratum, with at least 10 units in every reported expertise-by-complexity cell. If those thresholds are not met, the release may publish feasibility metrics for the collected packets but must not make model-vs-human ranking claims. The preferred design samples from the same benchmark case-mix strata used by the leaderboard so simple, multi-claim, multi-defendant, mixed-doctrine, and complex packets are all represented.

## Blinding

Human reviewers receive the frozen model-visible packet, unit list, and instructions only. They do not receive the model identity, model probability, model rationale, final case outcome, ground-truth label, or other reviewers' forecasts until after forecasts are locked. The packet time limit is 45 minutes unless a future protocol version states otherwise.

## Forecast Task

For each prediction unit, reviewers enter a calibrated probability from 0 to 1 that the unit will be fully dismissed, confidence, minutes spent, and a short note. External research is prohibited unless a future protocol version marks a separate research-allowed arm; such an arm must be analyzed separately.

## Compensation

Reviewers are paid a fixed honorarium or fixed hourly amount disclosed in the cycle notes. Payment must not depend on accuracy, calibration, agreement with models, or agreement with other reviewers.

## Ethics Review

A human-baseline cycle whose results will support a publication or a public model-vs-human claim must obtain institutional review board approval or a documented exemption determination before recruitment begins, and the cycle notes must state which applies. Internal pilot or calibration exercises that are never reported publicly do not require prior review but still follow the consent, blinding, and compensation rules above.

## Scoring And Reporting

Human forecasts are scored on the shared subset with the same Brier outcome labels used for model scoring. Model-vs-human comparisons require paired clustered bootstrap intervals over the shared units and must report the expertise strata, complexity strata, reviewer count, unit count, and any missing strata. Agreement-only summaries are allowed as diagnostics but are not sufficient for headline model-vs-human claims.

## Author Participation

Project authors and benchmark maintainers may write instructions, perform quality control, and review aggregate summaries, but they must not contribute forecasts to any reported human-baseline arm. If an author participates in a pilot or calibration exercise, those rows are excluded from reportable human-baseline scoring.
