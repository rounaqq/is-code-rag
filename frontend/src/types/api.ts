/**
 * TypeScript Data Models matching FastAPI Pydantic Schemas in src/api/main.py.
 * Zero invented or mocked structures; strictly matches backend responses.
 */

// -------------------------------------------------------------
// 1. Health & Audit Types
// -------------------------------------------------------------
export interface HealthStatus {
  status: string;
}

export interface LatencyStatistics {
  average: number;
  median_p50: number;
  p95: number;
  min: number;
  max: number;
}

export interface TopRetrievedClause {
  clause_id: string;
  retrieval_count: number;
}

export interface RecentQuery {
  timestamp?: string;
  key_name?: string;
  query?: string;
  latency_ms?: number;
  status_code?: number;
  top_clause?: string;
}

export interface AuditSummaryData {
  status: string;
  total_queries_logged: number;
  latency_statistics_ms?: LatencyStatistics;
  status_code_distribution?: Record<string, number>;
  top_retrieved_clauses?: TopRetrievedClause[];
  unique_authorized_keys?: string[];
  recent_queries?: RecentQuery[];
  message?: string;
}

// -------------------------------------------------------------
// 2. RAG & Clause Retrieval Types
// -------------------------------------------------------------
export interface ClauseHit {
  chunk_id: string;
  code?: string;
  clause?: string;
  title: string;
  text: string;
  context_path?: string;
  page_number?: number;
  score?: number;
  confidence_score?: number;
  rerank_score?: number;
  verified?: boolean;
}

export interface MultiCodeQueryResponse {
  query: string;
  code_filter: string;
  total_results: number;
  results: ClauseHit[];
}

// -------------------------------------------------------------
// 3. Structural Sizing & CAD Models
// -------------------------------------------------------------

// Beams (IS 456 Cl. 26.5.1 & Table 19)
export interface BeamSizingParams {
  span_m: number;
  dead_load_kN_per_m: number;
  live_load_kN_per_m: number;
  fck?: number;
  fy?: number;
  exposure?: string;
  max_aggregate_size_mm?: number;
}

export interface BeamDesignDict {
  b: number;
  D: number;
  d: number;
  fck: number;
  fy: number;
  exposure: string;
  cover_mm: number;
  main_bar_dia_mm: number;
  main_bar_count: number;
  ast_provided_mm2: number;
  compression_bar_dia_mm: number;
  compression_bar_count: number;
  stirrup_dia_mm: number;
  stirrup_spacing_mm: number;
  stirrup_legs: number;
  tau_v?: number;
  tau_c?: number;
  span_m?: number;
  approval_status?: string;
}

export interface BeamSizingResponse {
  status: string;
  reason?: string;
  design?: BeamDesignDict;
  design_dict?: BeamDesignDict;
  sizing?: {
    design_dict: BeamDesignDict;
    is456_citations?: string[];
  };
  review_sheet?: {
    checks: Record<string, any>;
    assumptions: Array<{ assumption: string; value: string; clause: string }>;
    markdown_report?: string;
  };
  review_report?: {
    approval_status?: string;
    checks?: Array<any>;
    assumptions?: Array<any>;
    markdown_report?: string;
  };
}

// Columns (IS 456 Cl. 26.5.3 & Cl. 39.3)
export interface ColumnSizingParams {
  axial_load_kN: number;
  length_m?: number;
  b_mm?: number;
  D_mm?: number;
  fck?: number;
  fy?: number;
  exposure?: string;
}

export interface ColumnSizingResponse {
  status: string;
  section_dimensions: string;
  width_mm: number;
  depth_mm: number;
  factored_axial_load_Pu_kN: number;
  axial_capacity_Pu_kN: number;
  rebar_selected: {
    bar_count: number;
    bar_diameter_mm: number;
    ast_provided_mm2: number;
    callout: string;
  };
  lateral_ties: {
    tie_diameter_mm: number;
    tie_pitch_mm: number;
    callout: string;
  };
  checks: Record<string, any>;
  governing_clauses?: string[];
}

// Slabs (IS 456 Cl. 24 & Cl. 26.5.2)
export interface SlabSizingParams {
  lx_m: number;
  ly_m: number;
  live_load_kN_m2: number;
  floor_finish_kN_m2?: number;
  support_width_mm?: number;
  fck?: number;
  fy?: number;
  exposure?: string;
  support_condition?: string;
}

export interface SlabSizingResponse {
  status: string;
  slab_type: string;
  aspect_ratio: number;
  geometry: {
    shorter_span_Lx_m: number;
    longer_span_Ly_m: number;
    overall_depth_D_mm: number;
    effective_depth_d_mm: number;
    nominal_cover_mm: number;
  };
  flexure: {
    main_rebar_x: {
      bar_dia_mm: number;
      spacing_mm: number;
      callout: string;
      ast_provided_mm2_per_m: number;
    };
    transverse_reinforcement: {
      rebar: {
        bar_dia_mm: number;
        spacing_mm: number;
        callout: string;
      };
    };
  };
  checks: Record<string, any>;
  governing_clauses?: string[];
}

// Footings (IS 456 Cl. 34)
export interface FootingSizingParams {
  axial_load_kN: number;
  sbc_kN_m2?: number;
  col_b_mm?: number;
  col_D_mm?: number;
  fck?: number;
  fy?: number;
}

export interface FootingSizingResponse {
  status: string;
  geometry: {
    B_mm: number;
    L_mm: number;
    total_depth_D_mm: number;
    effective_depth_d_mm: number;
    area_provided_m2: number;
  };
  flexure: {
    rebar_mesh: {
      bar_dia_mm: number;
      spacing_mm: number;
      bar_count: number;
      callout: string;
    };
  };
  checks: Record<string, any>;
  governing_clauses?: string[];
}

// Generic CAD Export Return
export interface CADExportResponse {
  status: string;
  dxf_path: string;
  approval_status?: string;
  section_dimensions?: string;
  rebar?: string;
  ties?: string;
  plan_dimensions?: string;
  total_depth?: number;
  reinforcement?: string;
  slab_type?: string;
  dimensions?: string;
  notes?: string;
}

// Engineer Review & Sign-Off
export interface EngineerReviewSignoffPayload {
  design?: any;
  span_m?: number;
  dead_load_kN_per_m?: number;
  live_load_kN_per_m?: number;
  fck?: number;
  fy?: number;
  exposure?: string;
  overrides?: Record<string, any>;
  reviewer_name: string;
  reviewer_role: string;
  review_date: string;
  outcome?: string;
  remarks?: string;
}
