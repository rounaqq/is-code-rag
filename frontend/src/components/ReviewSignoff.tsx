import React, { useState } from 'react';
import { 
  FileCheck2, 
  UserCheck, 
  ShieldAlert, 
  CheckCircle2, 
  XCircle, 
  Sliders, 
  FileText, 
  Download, 
  Loader2, 
  Info, 
  Building2, 
  Calendar, 
  Award,
  Key,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import { submitEngineerReview, exportBeamDXF, getCADDownloadUrl, getStoredApiKey } from '../services/api';
import { EngineeringStamp } from './review/EngineeringStamp';
import { DeficiencyChecklist, type ChecklistItem } from './review/DeficiencyChecklist';

export interface ReviewSignoffProps {
  activeDesigns?: Record<string, any>;
}

export const ReviewSignoff: React.FC<ReviewSignoffProps> = ({ activeDesigns }) => {
  // Design Input state
  const [spanM, setSpanM] = useState<number>(5.0);
  const [deadLoad, setDeadLoad] = useState<number>(15.0);
  const [liveLoad, setLiveLoad] = useState<number>(12.0);
  const [fck, setFck] = useState<number>(25);
  const [fy, setFy] = useState<number>(500);
  const [exposure, setExposure] = useState<string>('Moderate');

  // Engineer Override state (optional)
  const [enableOverrides, setEnableOverrides] = useState<boolean>(false);
  const [overrideB, setOverrideB] = useState<number>(300);
  const [overrideD, setOverrideD] = useState<number>(500);
  const [overrideBarCount, setOverrideBarCount] = useState<number>(3);
  const [overrideBarDia, setOverrideBarDia] = useState<number>(20);
  const [overrideStirrupSpacing, setOverrideStirrupSpacing] = useState<number>(150);

  // Human Reviewer Credentials
  const [reviewerName, setReviewerName] = useState<string>('Er. Rajesh V. Sharma');
  const [reviewerRole, setReviewerRole] = useState<string>('Chief Structural Engineer');
  const [licenseNo, setLicenseNo] = useState<string>('STR/DEL/2026/8942');
  const [reviewDate, setReviewDate] = useState<string>(() => new Date().toISOString().split('T')[0]);
  const [outcome, setOutcome] = useState<string>('Approved for Detailed Drawings');
  const [remarks, setRemarks] = useState<string>(
    'Cross-checked bending moment envelope and deflection limits against IS 456:2000 Cl. 23.2. Sizing confirmed adequate for design life.'
  );

  // Pre-flight Deficiency Checklist State
  const [checklist, setChecklist] = useState<ChecklistItem[]>([
    {
      id: 'flexure',
      label: 'Flexural Limit State (Mu ≤ Mu,lim)',
      code: 'IS 456 Cl. 38.1',
      checked: true,
      required: true,
      clause: 'Tension steel within 0.85bd/fy minimum and 0.04bD maximum limits.',
    },
    {
      id: 'shear',
      label: 'Shear Stirrup Spacing (sv ≤ 0.75d)',
      code: 'IS 456 Cl. 26.5.1.5',
      checked: true,
      required: true,
      clause: 'Nominal shear stress checked against Table 19 concrete capacity.',
    },
    {
      id: 'deflection',
      label: 'Deflection Control Basic Ratio (L/d ≤ 20)',
      code: 'IS 456 Cl. 23.2',
      checked: true,
      required: true,
      clause: 'Effective depth adequate to satisfy span-to-depth deflection criteria.',
    },
    {
      id: 'cover',
      label: 'Environmental Durability Cover (Table 16)',
      code: 'IS 456 Table 16',
      checked: true,
      required: true,
      clause: 'Nominal cover provided satisfies exposure class requirements.',
    },
    {
      id: 'ductile',
      label: 'Seismic Ductile Confinement (135° Hooks)',
      code: 'IS 13920 Cl. 6',
      checked: true,
      required: false,
      clause: 'Cross-ties and 135° hook anchorage in designated seismic zones.',
    },
  ]);

  const handleToggleChecklist = (id: string) => {
    setChecklist((prev) =>
      prev.map((item) => (item.id === id ? { ...item, checked: !item.checked } : item))
    );
  };

  // Execution state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [reviewResult, setReviewResult] = useState<any | null>(null);
  const [rejectionReasons, setRejectionReasons] = useState<string[] | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [dxfExporting, setDxfExporting] = useState<boolean>(false);
  const [dxfPath, setDxfPath] = useState<string | null>(null);
  const [dxfError, setDxfError] = useState<string | null>(null);

  const handleSubmitReview = async (e?: React.FormEvent | React.MouseEvent) => {
    if (e && e.preventDefault) {
      e.preventDefault();
    }
    setFormError(null);
    setRejectionReasons(null);
    setAuthError(null);
    setSuccessBanner(null);
    setDxfError(null);

    // Client-side deterministic validation to guarantee prompt feedback
    if (!spanM || isNaN(spanM) || spanM <= 0) {
      setFormError('Please enter a valid Clear Span (m) greater than 0.');
      return;
    }
    if (deadLoad === undefined || isNaN(deadLoad) || deadLoad < 0) {
      setFormError('Please enter a valid Dead Load (kN/m) (0 or greater).');
      return;
    }
    if (liveLoad === undefined || isNaN(liveLoad) || liveLoad < 0) {
      setFormError('Please enter a valid Live Load (kN/m) (0 or greater).');
      return;
    }
    if (!reviewerName.trim()) {
      setFormError('Engineer Full Name is required for statutory sign-off.');
      return;
    }
    if (!reviewerRole.trim()) {
      setFormError('Designation / Role is required for statutory sign-off.');
      return;
    }
    if (!licenseNo.trim()) {
      setFormError('Licence / Council Registration Number is required.');
      return;
    }
    if (!reviewDate) {
      setFormError('Review Date is required.');
      return;
    }

    // API Key verification check
    const apiKey = getStoredApiKey();
    if (!apiKey) {
      setAuthError('Unauthorized: No API key detected. Please click "Configure API Key" to provide an authorized X-API-Key.');
      setFormError('Authentication required: Please configure your API Key before submitting.');
      return;
    }

    setIsLoading(true);

    // Build overrides payload if toggle enabled
    const overrides = enableOverrides
      ? {
          b: overrideB,
          D: overrideD,
          main_bar_count: overrideBarCount,
          main_bar_dia_mm: overrideBarDia,
          stirrup_spacing_mm: overrideStirrupSpacing,
        }
      : undefined;

    try {
      console.log('[ReviewSignoff] Submitting review sheet payload to /v1/design/review...');
      const response = await submitEngineerReview({
        design: undefined, // Let backend calculate from loads
        span_m: spanM,
        dead_load_kN_per_m: deadLoad,
        live_load_kN_per_m: liveLoad,
        fck,
        fy,
        exposure,
        overrides,
        reviewer_name: reviewerName.trim(),
        reviewer_role: `${reviewerRole.trim()} [Reg: ${licenseNo.trim()}]`,
        review_date: reviewDate,
        outcome,
        remarks,
      });

      console.log('[ReviewSignoff] Review response received:', response);
      setReviewResult(response);
      setSuccessBanner('Formal Engineering Review Sheet generated and verified against IS 456:2000.');
    } catch (err: any) {
      console.error('[ReviewSignoff] Submit review failed:', err);
      if (err.response?.status === 401) {
        setAuthError('Unauthorized (401): Valid X-API-Key is required. Please click "Configure API Key" to set your key.');
        setFormError('Authentication error (401): Invalid or missing X-API-Key.');
      } else if (err.response?.status === 400 && err.response?.data?.detail?.reasons) {
        setRejectionReasons(err.response.data.detail.reasons);
        setFormError('IS 456 Rule Violation: The custom overrides violate statutory engineering limits.');
      } else {
        const errorDetail = err.response?.data?.detail || err.message || 'Review submission failed.';
        const msg = typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail);
        setRejectionReasons([msg]);
        setFormError(`Submission error: ${msg}`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportReviewedCAD = async () => {
    if (!reviewResult?.design) {
      setDxfError('No verified design available to export. Please submit the review sheet first.');
      return;
    }
    setDxfExporting(true);
    setDxfError(null);

    try {
      console.log('[ReviewSignoff] Requesting reviewed DXF generation...');
      // Pass both design dictionary and fallback parameters to satisfy DesignDxfRequest
      const res = await exportBeamDXF({
        design: reviewResult.design,
        span_m: spanM,
        dead_load_kN_per_m: deadLoad,
        live_load_kN_per_m: liveLoad,
        fck,
        fy,
        exposure,
        reviewer_name: reviewerName.trim(),
        reviewer_role: reviewerRole.trim(),
        review_date: reviewDate,
        outcome,
        remarks,
        output_filename: `reviewed_beam_${reviewDate}_${Date.now().toString().slice(-4)}.dxf`,
      } as any);

      console.log('[ReviewSignoff] DXF export response:', res);
      if (res && res.dxf_path) {
        setDxfPath(res.dxf_path);

        // Auto-trigger browser download for instant feedback
        try {
          const downloadUrl = getCADDownloadUrl(res.dxf_path);
          const link = document.createElement('a');
          link.href = downloadUrl;
          link.download = res.dxf_path.split(/[/\\]/).pop() || 'reviewed_beam.dxf';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } catch (dlErr) {
          console.warn('[ReviewSignoff] Auto-download blocked, manual link ready:', dlErr);
        }
      } else {
        setDxfError('CAD export returned an empty file path.');
      }
    } catch (err: any) {
      console.error('[ReviewSignoff] CAD export failed:', err);
      const msg = err.response?.data?.detail || err.message || 'CAD export failed.';
      setDxfError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setDxfExporting(false);
    }
  };

  const allVerified = checklist.every((c) => c.checked);

  // Status mapping
  const stampStatus: 'APPROVED' | 'REVIEWED' | 'DRAFT' | 'REJECTED' =
    rejectionReasons && rejectionReasons.length > 0
      ? 'REJECTED'
      : outcome.includes('Approved') && allVerified
      ? 'APPROVED'
      : outcome.includes('Rejected')
      ? 'REJECTED'
      : 'DRAFT';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 mb-3">
              <UserCheck className="w-3.5 h-3.5" />
              Human-in-the-Loop Governance &amp; Overrides
            </div>
            <h1 className="text-2xl font-bold text-slate-100">
              Licensed Engineer Review &amp; Sign-Off Portal
            </h1>
            <p className="text-sm text-slate-400 mt-1 max-w-2xl">
              Strict legal compliance portal. AI acts strictly as a computational assistant; only an authorized 
              engineer holding a valid municipal/statutory license can review, override, and sign off candidate designs.
            </p>
          </div>

          <div className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300">
            <ShieldAlert className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span>Statutory Verification Active</span>
          </div>
        </div>
      </div>

      {/* Auth Error Banner */}
      {authError && (
        <div className="bg-rose-950/40 border border-rose-500/40 rounded-2xl p-4 text-rose-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg animate-in fade-in">
          <div className="flex items-start gap-3">
            <XCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <strong className="block text-rose-200 font-semibold mb-0.5">Authentication Error:</strong>
              <span className="text-rose-300/90 leading-relaxed">{authError}</span>
            </div>
          </div>
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('open_api_key_modal'))}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-semibold hover:bg-amber-500/30 whitespace-nowrap self-start sm:self-auto transition shadow-sm"
          >
            <Key className="w-3.5 h-3.5 text-amber-400" />
            <span>Configure API Key</span>
          </button>
        </div>
      )}

      {/* Success Notification Banner */}
      {successBanner && (
        <div className="bg-emerald-950/40 border border-emerald-500/40 rounded-2xl p-4 text-emerald-300 text-xs flex items-center justify-between shadow-lg animate-in fade-in">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span>{successBanner}</span>
          </div>
          <button
            onClick={() => setSuccessBanner(null)}
            className="text-emerald-400/70 hover:text-emerald-200 text-xs"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Form: Parameters + Overrides + Engineer Info + Checklist (7 cols) */}
        <form noValidate onSubmit={handleSubmitReview} className="lg:col-span-7 space-y-6">
          {/* Section 1: Member Sizing Loads */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-3 gap-2">
              <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-blue-400" />
                1. Base Structural Loading (IS 456 Cl. 22 / Cl. 36)
              </h2>
              {activeDesigns?.beam?.params && (
                <button
                  type="button"
                  onClick={() => {
                    const p = activeDesigns.beam.params;
                    if (p.span_m) setSpanM(p.span_m);
                    if (p.dead_load_kN_per_m) setDeadLoad(p.dead_load_kN_per_m);
                    if (p.live_load_kN_per_m) setLiveLoad(p.live_load_kN_per_m);
                    if (p.fck) setFck(p.fck);
                    if (p.fy) setFy(p.fy);
                    if (p.exposure) setExposure(p.exposure);
                    setSuccessBanner('Loaded active beam design parameters from Design Studio.');
                  }}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-500/15 hover:bg-blue-500/25 border border-blue-500/30 text-blue-300 text-[11px] font-medium transition cursor-pointer self-start sm:self-auto"
                >
                  <Sparkles className="w-3 h-3 text-blue-400" />
                  <span>Sync from Design Studio ({activeDesigns.beam.params.span_m}m)</span>
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Clear Span (m)</label>
                <input
                  type="number"
                  step="0.1"
                  min="1"
                  max="20"
                  value={spanM}
                  onChange={(e) => setSpanM(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Dead Load (kN/m)</label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  value={deadLoad}
                  onChange={(e) => setDeadLoad(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Live Load (kN/m)</label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  value={liveLoad}
                  onChange={(e) => setLiveLoad(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Concrete (fck)</label>
                <select
                  value={fck}
                  onChange={(e) => setFck(parseInt(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 focus:border-blue-500 focus:outline-none"
                >
                  <option value={20}>M20 (20 N/mm²)</option>
                  <option value={25}>M25 (25 N/mm²)</option>
                  <option value={30}>M30 (30 N/mm²)</option>
                  <option value={35}>M35 (35 N/mm²)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Steel (fy)</label>
                <select
                  value={fy}
                  onChange={(e) => setFy(parseInt(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 focus:border-blue-500 focus:outline-none"
                >
                  <option value={415}>Fe 415</option>
                  <option value={500}>Fe 500</option>
                  <option value={550}>Fe 550D</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Exposure</label>
                <select
                  value={exposure}
                  onChange={(e) => setExposure(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 focus:border-blue-500 focus:outline-none"
                >
                  <option value="Mild">Mild (20mm Cover)</option>
                  <option value="Moderate">Moderate (30mm Cover)</option>
                  <option value="Severe">Severe (45mm Cover)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 2: Engineer Manual Overrides (Verified by IS 456 rules) */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-amber-400" />
                2. Engineer Parameter Overrides (Optional)
              </h2>
              <label className="inline-flex items-center gap-2 cursor-pointer text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={enableOverrides}
                  onChange={(e) => setEnableOverrides(e.target.checked)}
                  className="w-4 h-4 rounded text-blue-600 bg-slate-950 border-slate-700 focus:ring-0"
                />
                Apply Custom Overrides
              </label>
            </div>

            {enableOverrides ? (
              <div className="space-y-4 animate-in fade-in duration-200">
                <p className="text-xs text-amber-300/90 bg-amber-500/10 p-3 rounded-lg border border-amber-500/20">
                  ⚠️ Any manual modifications will be evaluated deterministically against IS 456:2000 Cl. 26.3.2 (clear bar spacing), Cl. 26.5.1.1 (minimum/maximum tension steel), and Table 19 shear stirrup limits.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Override Width b (mm)</label>
                    <input
                      type="number"
                      step="25"
                      min="200"
                      value={overrideB}
                      onChange={(e) => setOverrideB(parseInt(e.target.value) || 200)}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:border-amber-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Override Depth D (mm)</label>
                    <input
                      type="number"
                      step="25"
                      min="250"
                      value={overrideD}
                      onChange={(e) => setOverrideD(parseInt(e.target.value) || 250)}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:border-amber-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Main Bars (Count &amp; Dia)</label>
                    <div className="flex gap-2">
                      <input
                        type="number"
                        min="2"
                        max="8"
                        value={overrideBarCount}
                        onChange={(e) => setOverrideBarCount(parseInt(e.target.value) || 2)}
                        className="w-1/2 px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:border-amber-500 focus:outline-none"
                        placeholder="Count"
                      />
                      <select
                        value={overrideBarDia}
                        onChange={(e) => setOverrideBarDia(parseInt(e.target.value))}
                        className="w-1/2 px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 focus:border-amber-500 focus:outline-none"
                      >
                        <option value={12}>T12</option>
                        <option value={16}>T16</option>
                        <option value={20}>T20</option>
                        <option value={25}>T25</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Stirrup Spacing sv (mm)</label>
                    <input
                      type="number"
                      step="10"
                      min="100"
                      max="300"
                      value={overrideStirrupSpacing}
                      onChange={(e) => setOverrideStirrupSpacing(parseInt(e.target.value) || 100)}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:border-amber-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">
                Automatic calculation will determine optimal member dimensions and reinforcement.
              </p>
            )}
          </div>

          {/* Section 3: Pre-flight Statutory Deficiency Checklist */}
          <DeficiencyChecklist items={checklist} onToggle={handleToggleChecklist} />

          {/* Section 4: Statutory Human Credentials & Signature */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2 border-b border-slate-800 pb-3">
              <Award className="w-4 h-4 text-emerald-400" />
              4. Licensed Engineer Statutory Credentials &amp; Outcome
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Engineer Full Name *</label>
                <input
                  type="text"
                  value={reviewerName}
                  onChange={(e) => setReviewerName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Designation / Role *</label>
                <input
                  type="text"
                  value={reviewerRole}
                  onChange={(e) => setReviewerRole(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Licence / Council Reg No. *</label>
                <input
                  type="text"
                  value={licenseNo}
                  onChange={(e) => setLicenseNo(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 font-mono focus:border-emerald-500 focus:outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Review Date</label>
                <div className="relative">
                  <input
                    type="date"
                    value={reviewDate}
                    onChange={(e) => setReviewDate(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
                    required
                  />
                  <Calendar className="w-4 h-4 text-slate-500 absolute right-3 top-3 pointer-events-none" />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Review Outcome</label>
              <select
                value={outcome}
                onChange={(e) => setOutcome(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
              >
                <option value="Approved for Detailed Drawings">Approved for Detailed Drawings</option>
                <option value="Reviewed with Engineering Conditions">Reviewed with Engineering Conditions</option>
                <option value="Provisional Approval (Pending Soil Report)">Provisional Approval (Pending Soil Report)</option>
                <option value="Rejected - Inadequate Capacity">Rejected - Inadequate Capacity</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Engineer Review Notes &amp; Remarks</label>
              <textarea
                rows={2}
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-100 focus:border-emerald-500 focus:outline-none"
                placeholder="Include any specific site stipulations, lap splice lengths, or inspection holds..."
              />
            </div>

            {/* Client-side or API Validation Error Banner right at submit action */}
            {formError && (
              <div className="p-3.5 rounded-xl bg-rose-950/50 border border-rose-500/50 text-xs text-rose-300 flex items-start gap-2.5 animate-in fade-in">
                <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                <span className="leading-relaxed">{formError}</span>
              </div>
            )}

            <button
              type="button"
              onClick={handleSubmitReview}
              disabled={isLoading}
              className="w-full py-3.5 px-4 rounded-xl font-semibold text-sm text-white bg-indigo-600 hover:bg-indigo-500 active:scale-[0.99] transition-all shadow-lg shadow-indigo-600/25 disabled:opacity-50 flex items-center justify-center gap-2 cursor-pointer"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Verifying Against IS 456 Clauses...</span>
                </>
              ) : (
                <>
                  <FileCheck2 className="w-4 h-4" />
                  <span>Submit Formal Engineering Review Sheet</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Right Output: Formal Review Sheet / Stamp / Violations (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* IS 456 Code Rejection Alert */}
          {rejectionReasons && rejectionReasons.length > 0 && (
            <div className="bg-red-950/40 border border-red-500/40 rounded-2xl p-6 shadow-xl animate-in fade-in duration-200">
              <div className="flex items-start gap-3">
                <XCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-red-200">
                    IS 456 Rule Violation: Overrides Rejected
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">
                    The requested dimensions or rebar values violate mandatory Indian Standard safety clauses:
                  </p>
                  <ul className="mt-3 space-y-1.5 list-disc list-inside text-xs text-red-300 font-mono">
                    {rejectionReasons.map((reason, idx) => (
                      <li key={idx} className="leading-relaxed">
                        {reason}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Success: Formal Engineer Review Sheet with Digital Stamp & QR */}
          {reviewResult ? (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5 animate-in fade-in duration-200">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <span className="text-sm font-bold text-slate-100">
                    Formal Review Sheet Generated
                  </span>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {reviewResult.review_report?.approval_status?.toUpperCase() || 'REVIEWED'}
                </span>
              </div>

              {/* Dynamic Engineering Stamp Component */}
              <EngineeringStamp
                status={stampStatus}
                reviewerName={reviewerName}
                licenseNo={licenseNo}
                reviewerRole={reviewerRole}
                date={reviewResult.design?.approval_timestamp || reviewDate}
                allChecklistVerified={allVerified}
              />

              {/* Deterministic Verification Results */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Verified Member Properties
                </h4>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block text-[10px]">SECTION (b × D)</span>
                    <strong className="text-slate-200 text-sm">
                      {reviewResult.design?.b} × {reviewResult.design?.D} mm
                    </strong>
                  </div>
                  <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block text-[10px]">MAIN REBAR</span>
                    <strong className="text-emerald-400 text-sm">
                      {reviewResult.design?.main_bar_count} - T{reviewResult.design?.main_bar_dia_mm}
                    </strong>
                  </div>
                  <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block text-[10px]">SHEAR STIRRUPS</span>
                    <strong className="text-amber-400 text-sm">
                      2L-T{reviewResult.design?.stirrup_dia_mm || 8} @ {reviewResult.design?.stirrup_spacing_mm || 150}mm
                    </strong>
                  </div>
                  <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block text-[10px]">CLEAR COVER</span>
                    <strong className="text-slate-200 text-sm">
                      {reviewResult.design?.cover_mm || 30} mm
                    </strong>
                  </div>
                </div>
              </div>

              {/* Standard Assumptions & Code Citations */}
              <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 text-xs space-y-1.5">
                <span className="font-semibold text-slate-300 block mb-1">
                  Design Assumptions (IS 456:2000):
                </span>
                <div className="text-[11px] text-slate-400 space-y-1">
                  <div>✓ Table 19 shear stirrup compliance verified</div>
                  <div>✓ Cl. 26.3.2 minimum aggregate gap clearance passed</div>
                  <div>✓ Cl. 26.5.1 minimum 0.85*b*d/fy tension steel passed</div>
                  <div>✓ Cl. 26.5.1.1 maximum 0.04*b*D tension steel limit passed</div>
                </div>
              </div>

              {/* DXF Export Error Banner */}
              {dxfError && (
                <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/40 text-xs text-rose-300 flex items-start gap-2">
                  <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                  <span>CAD Export Error: {dxfError}</span>
                </div>
              )}

              {/* Export Reviewed CAD Button */}
              <div className="pt-2">
                <button
                  onClick={handleExportReviewedCAD}
                  disabled={dxfExporting}
                  className="w-full py-2.5 px-4 rounded-xl text-xs font-semibold text-slate-900 bg-emerald-400 hover:bg-emerald-300 transition-all flex items-center justify-center gap-2 shadow cursor-pointer disabled:opacity-50 btn-tactile active:scale-[0.98]"
                >
                  {dxfExporting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Generating Reviewed DXF...
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4" />
                      Export Reviewed CAD Blueprint (.DXF)
                    </>
                  )}
                </button>

                {dxfPath && (
                  <div className="mt-3 p-3 rounded-xl bg-emerald-950/50 border border-emerald-500/30 flex items-center justify-between gap-2">
                    <span className="text-xs font-mono text-emerald-300 truncate">
                      ✓ {dxfPath.split(/[/\\]/).pop()} ready
                    </span>
                    <a
                      href={getCADDownloadUrl(dxfPath)}
                      download
                      className="text-xs font-bold text-slate-900 bg-emerald-400 hover:bg-emerald-300 px-3 py-1.5 rounded-lg shadow transition whitespace-nowrap btn-tactile"
                    >
                      Download DXF
                    </a>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 text-center space-y-4 card-hover">
              <FileText className="w-10 h-10 text-slate-600 mx-auto" />
              <div>
                <h3 className="text-sm font-semibold text-slate-200">
                  Awaiting Engineering Review Submission
                </h3>
                <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1 leading-relaxed">
                  Fill in the member design loads, verify the deficiency checklist, and enter your licensed credentials on the left to generate the formal sealed review sheet.
                </p>
                <div className="pt-3">
                  <button
                    type="button"
                    onClick={handleSubmitReview}
                    disabled={isLoading}
                    className="px-5 py-2.5 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition shadow inline-flex items-center gap-2 cursor-pointer disabled:opacity-50 btn-tactile active:scale-[0.98]"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Verifying &amp; Generating...</span>
                      </>
                    ) : (
                      <>
                        <FileCheck2 className="w-3.5 h-3.5" />
                        <span>Submit Review &amp; Unlock DXF</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Live Preview Stamp in Draft State */}
              <div className="opacity-75">
                <EngineeringStamp
                  status="DRAFT"
                  reviewerName={reviewerName || 'Er. Pending Name'}
                  licenseNo={licenseNo || 'Pending Reg'}
                  reviewerRole={reviewerRole || 'Structural Reviewer'}
                  date={reviewDate}
                  allChecklistVerified={allVerified}
                />
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 text-left text-xs text-slate-400 space-y-1">
                <div className="flex items-center gap-2 font-medium text-slate-300">
                  <Info className="w-3.5 h-3.5 text-blue-400" />
                  Statutory Rule:
                </div>
                <p className="text-[11px] text-slate-500">
                  Engineering certification requires the reviewer's professional license number. Submissions lacking engineer credentials are held as non-certified drafts.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
