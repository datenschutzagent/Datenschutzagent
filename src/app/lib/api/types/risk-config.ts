/**
 * TypeScript-Spiegel der Backend-Pydantic-Models in
 * `backend/app/services/risk_config_loader.py`.
 *
 * Wir senden / empfangen die Config als JSON; das Backend validiert mit
 * RiskConfig.model_validate und schreibt YAML.
 */

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface AvvLevelThreshold {
  max_score: number;
  level: RiskLevel;
}

export interface AvvScoreNormalization {
  score_min: number;
  score_max: number;
}

export interface AvvRiskConfig {
  level_thresholds: AvvLevelThreshold[];
  score_normalization: AvvScoreNormalization;
  dimension_weights: Record<string, number>;
  min_confidence: number;
}

export interface DsfaScreeningFactor {
  id: string;
  label: string;
  description: string;
  weight: number;
  keywords_processing_context: string[];
  keywords_title: string[];
  case_flag: string | null;
  findings_severity: string[];
}

export interface DsfaScreeningConfig {
  required_threshold: number;
  factors: DsfaScreeningFactor[];
}

export interface DsfaAssessmentConfig {
  scale_type: "1-3" | "1-5";
  scale_labels: {
    likelihood: Record<number, string>;
    severity: Record<number, string>;
  };
  matrix: Record<string, RiskLevel>;
  dpo_consultation_required_when_residual_in: RiskLevel[];
  min_confidence: number;
}

export interface CaseScoreConfig {
  severity_weights: Record<string, number>;
  max_score: number;
}

export interface MaturityVelocityConfig {
  optimal_days: number;
  worst_days: number;
}

export interface MaturityConfig {
  weights: Record<string, number>;
  velocity: MaturityVelocityConfig;
}

export interface RiskVelocityConfig {
  enabled: boolean;
  window_days: number;
  significant_change_pct: number;
}

export interface MitigationReduction {
  score_delta: number;
  dimension_deltas: Record<string, number>;
  likelihood_delta: number;
  severity_delta: number;
  applicable_risk_keywords: string[];
}

export interface MitigationCatalogEntry {
  id: string;
  label: string;
  description: string;
  applies_to: "avv" | "dsfa" | "both";
  tom_category: string | null;
  evidence_required: boolean;
  reduction: MitigationReduction;
}

export interface MitigationCatalogConfig {
  enabled: boolean;
  min_likelihood: number;
  min_severity: number;
  min_avv_score: number;
  catalog: MitigationCatalogEntry[];
}

export interface RiskConfig {
  version: number;
  avv: AvvRiskConfig;
  dsfa_screening: DsfaScreeningConfig;
  dsfa_assessment: DsfaAssessmentConfig;
  case_score: CaseScoreConfig;
  maturity: MaturityConfig;
  risk_velocity: RiskVelocityConfig;
  mitigations: MitigationCatalogConfig;
}

export interface AdminRiskConfigResponse {
  config: RiskConfig;
  profile: string;
  path: string | null;
  is_default: boolean;
}

export interface AdminRiskConfigPreviewSample {
  name: string;
  inputs: Record<string, unknown>;
  current: Record<string, unknown>;
  preview: Record<string, unknown>;
}

export interface AdminRiskConfigPreviewResponse {
  samples: AdminRiskConfigPreviewSample[];
}
