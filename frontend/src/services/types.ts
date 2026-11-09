export type Kind = 'real' | 'imported' | 'mock' | 'pending'
export interface Project { id: string; name: string; description: string; stack: string[]; status: 'built'|'pending'|'demo'; data_kind: Kind; last_updated: string|null; thumbnail: string|null; preview_url: string|null
  client?: string; category?: string; repo?: string; build_status?: string; test_status?: string; synthetic?: boolean; launch_label?: string; import_note?: string }
export interface Node { name: string; path: string; type: 'file'|'dir'; category?: string; change?: string; children: Node[] }
export interface FileContent { path: string; language: string; content: string; original: string|null; binary: boolean; change: string }
export interface DiffFile { path: string; status: 'added'|'modified'|'deleted'; additions: number; deletions: number; diff: string }
export interface Step { n: number; title: string; status: 'completed'|'partial'|'pending'|'blocked'; timestamp: string|null; description: string; output: string; evidence: string }
export interface Suite { id: string; title: string; command: string; ran_at: string; exit_code: number; cases: {name:string;class:string;status:string}[]; output_tail: string[] }
export interface Tests { generated_at: string; build?: { status: string; command: string; ran_at: string }; suites: Suite[]; totals: { passed: number; failed: number } }
export interface PlanItem { n: number; task: string; files: string; tools: string; status: string; evidence: string }
export interface Analysis { repository: Record<string,any>; requirements_source: {document:string;access:string}; requirements: {id:string;area:string;text:string;original:string;result:string;evidence:string}[]; tools: {name:string;decision:string;reason:string}[]; plan: (string | PlanItem)[]; limitations: string[]
  existing_issues?: { id: string; area: string; finding: string; observed: string }[]; environment?: Record<string, string | null>
  dataset?: { file: string; sha256: string; observations: number; cities: { city: string; observations: number; first_date: string; last_date: string; missing_calendar_days: number; temp_min_c: number; temp_max_c: number }[]; date_range: string[]; columns: { column: string; type: string; missing: number; example: string }[]; temperature_columns: string[]; context_columns: string[]; missing_values: number; malformed_observations: number; duplicate_observations: number; excluded_rows: number; synthetic: boolean; synthetic_evidence: string }
  method?: { name: string; candidates: string[]; why: string; how: string; limitations: string; why_not_ml: string }
  architecture?: { step: string; module: string; detail: string }[] }
export interface Git { repository_url: string; base_branch: string; base_branch_verified: boolean; base_branch_evidence?: string; import_kind?: string; dev_branch: string; baseline_commit: Record<string,string>; commits: Record<string,string>[]; push: {status:string;reason:string;attempted_at?:string;output?:string}; draft_pr: {status:string;url:string|null;reason:string} }
export interface Overview { data_note: string; total_projects: number; placeholder_projects?: number; built_projects: number; tests_passed: number; failed_builds: number; active_agent_tasks: number; pull_requests: number; pull_requests_note: string; summary: Record<string, number|boolean>; summaries?: Record<string, Record<string, number|boolean>> }

// ---- Prompt B weather evaluation (evaluation.json)
export interface HorizonMae { horizon: number; n: number; mae: number | null; sum_abs_error: number }
export interface CityEval {
  city: string; formula: string; explanation: string; baseline_recent_average_mae: number | null
  split: { strategy: string; description: string; shuffled: boolean; train_fraction: number | null; train_count: number; evaluation_count: number; train_start: string; train_end: string; evaluation_start: string; evaluation_end: string; no_leakage: boolean }
  selection: { method: string; label: string; period: number | null; train_backtest_mae: number; basis: string; candidates: { method: string; label: string; period: number | null; train_backtest_mae: number }[] }
  metrics: { by_horizon: HorizonMae[]; pooled: { n: number; mae: number | null }; train_only_fixed_origin: { n: number; mae: number | null; note: string } }
  evaluation_rows: { horizon: number; rows: { date: string; actual: number; predicted: number; abs_error: number }[] }[]
  comparison: { method: string; label: string; period: number | null; train_backtest_mae: number; heldout_mae: number | null; heldout_mae_by_horizon: (number | null)[]; selected: boolean }[]
}
export interface DemoCase { case: string; city: string; horizon_days: number; method: string; period_days: number | null; generated_on: string; last_observation_date: string; predictions: { day: number; date: string; predicted_temp_c: number; calculation: string }[]; heldout_mae_by_forecast_day: { day: number; mae: number | null; n: number }[]; heldout_mae_pooled: number | null; disclaimer: string }
export interface WeatherEvaluation {
  generated_at: string; synthetic_data: boolean; disclaimer: string
  overview: { cities: string[]; dataset: { file: string; total_rows: number; valid_rows: number; first_date: string; last_date: string; columns: string[] }; data_note: string; split: { description: string } }
  data_quality: { total_rows: number; valid_rows: number; excluded_total: number; malformed_total: number; duplicates_total: number; missing_values_total: number; excluded: { reason: string; description: string; count: number }[] }
  evaluation: { formula: string; split_config: { description: string }; cities: CityEval[]; overall: { n: number; mae: number | null; by_horizon: { horizon: number; n: number; mae: number | null }[] } }
  demonstrations: { cities: string[]; note: string; cases: DemoCase[] }
  robustness_checks: { name: string; group: string; input: string; outcome: string; passed: boolean }[]
  independent_check: { description: string; all_match: boolean; cities: { city: string; mae_reported: number; mae_independent: number; match: boolean }[] }
  synthetic_structure_check: Record<string, boolean>
  tests: { passed: number; failed: number; suites: { id: string; title: string; passed: number; failed: number }[] }
  known_limitations: string[]
}
