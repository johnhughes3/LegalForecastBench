/* Generated from docs/schemas/site-export-v1.schema.json. Run pnpm --filter @legalforecastbench/site contract:generate to update. */

export type ContaminationBoundary = string | null;
export type ExcludedCaseCount = number;
export type Lower = number;
export type MeanProbability = number | null;
export type ObservedRate = number | null;
export type UnitCount = number;
export type Upper = number;
export type Calibration = SiteCalibrationBin[];
export type CaseCount = number;
export type Basis = "unavailable" | "estimated_accounting";
export type CostPerCase = number | null;
export type CoveredCaseCount = number;
export type Currency = "USD";
export type MissingCaseCount = number;
export type StandardRateStatus = "unavailable";
export type StandardRateTotalCost = number | null;
export type TotalCost = number | null;
export type EqualCaseBrier = number;
export type Ablation = string | null;
export type ComparisonEligibility = "eligible" | "qualified" | "unknown";
export type Condition = "agentic" | "summary" | "full_text_one_shot" | "unknown";
export type DisplayName = string;
export type EligibilityReason = string;
export type ModelVersion = string | null;
export type Provider = string | null;
export type ReasoningEffort = string | null;
export type ThinkingLevel = string | null;
export type TrainingCutoff = string | null;
export type MicroBrier = number;
export type ModelId = string;
export type UnitCount1 = number;
export type Brier = number;
export type CaseId = string;
export type Outcome = 0 | 1;
export type ProbabilityFullyDismissed = number;
export type UnitId = string;
export type Units = SiteUnit[];
export type Results = SiteResult[];
export type SchemaVersion = "legalforecast-site-export-v1";
export type GeneratedAt = string | null;
export type ModelRegistrySha256 = string | null;
export type RunIdentitySha256 = string | null;

/**
 * Versioned site data generated only from scored, public benchmark outputs.
 */
export interface SiteExport {
  contamination_boundary: ContaminationBoundary;
  excluded_case_count: ExcludedCaseCount;
  results: Results;
  schema_version: SchemaVersion;
  source: SiteSource;
}
/**
 * One model/condition row, including its public unit-level explorer data.
 */
export interface SiteResult {
  calibration: Calibration;
  case_count: CaseCount;
  costs: SiteCosts;
  equal_case_brier: EqualCaseBrier;
  metadata: SiteModelMetadata;
  micro_brier: MicroBrier;
  model_id: ModelId;
  unit_count: UnitCount1;
  units: Units;
}
/**
 * Calibration values computed by the Python scorer.
 */
export interface SiteCalibrationBin {
  lower: Lower;
  mean_probability: MeanProbability;
  observed_rate: ObservedRate;
  unit_count: UnitCount;
  upper: Upper;
}
/**
 * Cost availability; missing accounting is never interpreted as free usage.
 */
export interface SiteCosts {
  basis: Basis;
  cost_per_case: CostPerCase;
  covered_case_count: CoveredCaseCount;
  currency?: Currency;
  missing_case_count: MissingCaseCount;
  standard_rate_status?: StandardRateStatus;
  standard_rate_total_cost?: StandardRateTotalCost;
  total_cost: TotalCost;
}
/**
 * A whitelist of display and experimental settings from a frozen registry.
 */
export interface SiteModelMetadata {
  ablation: Ablation;
  comparison_eligibility: ComparisonEligibility;
  condition: Condition;
  display_name: DisplayName;
  eligibility_reason: EligibilityReason;
  model_version: ModelVersion;
  provider: Provider;
  reasoning_effort: ReasoningEffort;
  thinking_level: ThinkingLevel;
  training_cutoff: TrainingCutoff;
}
/**
 * A public prediction unit, with no document content or execution details.
 */
export interface SiteUnit {
  brier: Brier;
  case_id: CaseId;
  outcome: Outcome;
  probability_fully_dismissed: ProbabilityFullyDismissed;
  unit_id: UnitId;
}
/**
 * Existing score provenance, without local paths or new identity machinery.
 */
export interface SiteSource {
  generated_at: GeneratedAt;
  model_registry_sha256: ModelRegistrySha256;
  run_identity_sha256: RunIdentitySha256;
}
