/**
 * Axios API Service configured for FastAPI backend.
 * Zero hardcoded secret keys; reads dynamically from browser localStorage
 * or optional build-time VITE_IS_RAG_API_KEY environment variable.
 */

import axios from 'axios';
import type {
  HealthStatus,
  AuditSummaryData,
  MultiCodeQueryResponse,
  BeamSizingParams,
  BeamSizingResponse,
  ColumnSizingParams,
  ColumnSizingResponse,
  SlabSizingParams,
  SlabSizingResponse,
  FootingSizingParams,
  FootingSizingResponse,
  CADExportResponse,
  EngineerReviewSignoffPayload,
} from '../types/api';

const API_BASE_URL = ''; // Relative path, handled by Vite proxy to http://127.0.0.1:8000

// Dynamic API Key Management (no secrets checked into source)
const API_KEY_STORAGE_KEY = 'is_rag_api_key';

export const getStoredApiKey = (): string => {
  const local = localStorage.getItem(API_KEY_STORAGE_KEY);
  if (local && local.trim() && local.trim() !== 'undefined' && local.trim() !== 'null') {
    return local.trim();
  }
  const envKey = import.meta.env.VITE_IS_RAG_API_KEY;
  if (envKey && typeof envKey === 'string' && envKey.trim() && envKey.trim() !== 'undefined') {
    return envKey.trim();
  }
  return '';
};

export const setStoredApiKey = (key: string): void => {
  if (key && key.trim()) {
    let cleanKey = key.trim();
    // Normalize if user copied 'name:key' format from server .env
    if (cleanKey.includes(':')) {
      const parts = cleanKey.split(':');
      cleanKey = parts[parts.length - 1].trim();
    }
    // Normalize if user prefixed with 'Bearer '
    if (cleanKey.toLowerCase().startsWith('bearer ')) {
      cleanKey = cleanKey.slice(7).trim();
    }
    localStorage.setItem(API_KEY_STORAGE_KEY, cleanKey);
  } else {
    localStorage.removeItem(API_KEY_STORAGE_KEY);
  }
  // Notify active listeners that the key has updated
  window.dispatchEvent(new Event('is_rag_api_key_changed'));
};

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Attach X-API-Key header dynamically if present
apiClient.interceptors.request.use((config) => {
  const key = getStoredApiKey();
  if (key) {
    if (config.headers && typeof config.headers.set === 'function') {
      config.headers.set('X-API-Key', key);
    } else {
      config.headers = config.headers || {};
      config.headers['X-API-Key'] = key;
    }
  }
  return config;
});

// -------------------------------------------------------------
// API Endpoint Functions
// -------------------------------------------------------------

// 1. Health & Observability
export const checkHealth = async (): Promise<HealthStatus> => {
  const resp = await apiClient.get<HealthStatus>('/health');
  return resp.data;
};

export const getAuditSummary = async (limit: number = 200): Promise<AuditSummaryData> => {
  const resp = await apiClient.get<AuditSummaryData>(`/v1/audit/summary?limit=${limit}`);
  return resp.data;
};

// 2. Multi-Standard RAG Search
export const searchISCodes = async (
  query: string,
  codeFilter?: string,
  topK: number = 5
): Promise<MultiCodeQueryResponse> => {
  const resp = await apiClient.post<MultiCodeQueryResponse>('/v1/rag/multicode/query', {
    query,
    code: codeFilter && codeFilter !== 'ALL' ? codeFilter : undefined,
    top_k: topK,
  });
  return resp.data;
};

// 3. Beam Sizing & CAD
export const sizeBeam = async (params: BeamSizingParams): Promise<BeamSizingResponse> => {
  const resp = await apiClient.post<BeamSizingResponse>('/v1/design/review', params);
  return resp.data;
};

export const exportBeamDXF = async (params: BeamSizingParams & { output_filename?: string }): Promise<CADExportResponse> => {
  const resp = await apiClient.post<CADExportResponse>('/v1/design/dxf', {
    ...params,
    output_filename: params.output_filename || 'beam_design.dxf',
  });
  return resp.data;
};

// 4. Column Sizing & CAD
export const sizeColumn = async (params: ColumnSizingParams): Promise<ColumnSizingResponse> => {
  const resp = await apiClient.post<ColumnSizingResponse>('/v1/design/column/review', params);
  return resp.data;
};

export const exportColumnDXF = async (params: ColumnSizingParams & { output_filename?: string }): Promise<CADExportResponse> => {
  const resp = await apiClient.post<CADExportResponse>('/v1/design/column/dxf', {
    ...params,
    output_filename: params.output_filename || 'column_design.dxf',
  });
  return resp.data;
};

// 5. Slab Sizing & CAD
export const sizeSlab = async (params: SlabSizingParams): Promise<SlabSizingResponse> => {
  const resp = await apiClient.post<SlabSizingResponse>('/v1/design/slab/review', params);
  return resp.data;
};

export const exportSlabDXF = async (params: SlabSizingParams & { output_filename?: string }): Promise<CADExportResponse> => {
  const resp = await apiClient.post<CADExportResponse>('/v1/design/slab/dxf', {
    ...params,
    output_filename: params.output_filename || 'slab_design.dxf',
  });
  return resp.data;
};

// 6. Footing Sizing & CAD
export const sizeFooting = async (params: FootingSizingParams): Promise<FootingSizingResponse> => {
  const resp = await apiClient.post<FootingSizingResponse>('/v1/design/footing/review', params);
  return resp.data;
};

export const exportFootingDXF = async (params: FootingSizingParams & { output_filename?: string }): Promise<CADExportResponse> => {
  const resp = await apiClient.post<CADExportResponse>('/v1/design/footing/dxf', {
    ...params,
    output_filename: params.output_filename || 'footing_design.dxf',
  });
  return resp.data;
};

// 7. Formal Engineer Review Sign-Off
export const submitEngineerReview = async (payload: EngineerReviewSignoffPayload): Promise<any> => {
  const resp = await apiClient.post('/v1/design/review', {
    design: payload.design,
    span_m: payload.span_m,
    dead_load_kN_per_m: payload.dead_load_kN_per_m,
    live_load_kN_per_m: payload.live_load_kN_per_m,
    fck: payload.fck,
    fy: payload.fy,
    exposure: payload.exposure,
    overrides: payload.overrides,
    reviewer_name: payload.reviewer_name,
    reviewer_role: payload.reviewer_role,
    review_date: payload.review_date,
    outcome: payload.outcome || 'Approved for Construction',
    remarks: payload.remarks,
  });
  return resp.data;
};

// 8. CAD Direct Download URL Helper
export const getCADDownloadUrl = (filepathOrFilename: string): string => {
  const filename = filepathOrFilename.split(/[/\\]/).pop() || filepathOrFilename;
  return `/v1/cad/download/${filename}`;
};
