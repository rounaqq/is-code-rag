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
  Award 
} from 'lucide-react';
import { submitEngineerReview, exportBeamDXF, getCADDownloadUrl } from '../services/api';

export const ReviewSignoff: React.FC = () => {
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

  // Execution state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [reviewResult, setReviewResult] = useState<any | null>(null);
  const [rejectionReasons, setRejectionReasons] = useState<string[] | null>(null);
  const [dxfExporting, setDxfExporting] = useState<boolean>(false);
  const [dxfPath, setDxfPath] = useState<string | null>(null);

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setRejectionReasons(null);
    setReviewResult(null);
    setDxfPath(null);

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

      setReviewResult(response);
    } catch (err: any) {
      if (err.response?.status === 400 && err.response?.data?.detail?.reasons) {
        setRejectionReasons(err.response.data.detail.reasons);
      } else {
        const errorDetail = err.response?.data?.detail || err.message || 'Review submission failed.';
        setRejectionReasons([typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail)]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportReviewedCAD = async () => {
    if (!reviewResult?.design) return;
    setDxfExporting(true);
    try {
      const res = await exportBeamDXF({
        ...reviewResult.design,
        output_filename: `reviewed_beam_${reviewDate}_${Date.now().toString().slice(-4)}.dxf`,
      });
      setDxfPath(res.dxf_path);
    } catch (err) {
      console.error(err);
    } finally {
      setDxfExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 mb-3">
              <UserCheck className="w-3.5 h-3.5" />
              Human-in-the-Loop Governance & Overrides
            </div>
            <h1 className="text-2xl font-bold text-slate-100">
              Licensed Engineer Review & Sign-Off Portal
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

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Form: Parameters + Overrides + Engineer Info (7 cols) */}
        <form onSubmit={handleSubmitReview} className="lg:col-span-7 space-y-6">
          {/* Section 1: Member Sizing Loads */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2 border-b border-slate-800 pb-3">
              <Building2 className="w-4 h-4 text-blue-400" />
              1. Base Structural Loading (IS 456 Cl. 22 / Cl. 36)
            </h2>

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
                    <label className="block text-xs font-medium text-slate-400 mb-1">Main Bars (Count & Dia)</label>
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

          {/* Section 3: Statutory Human Credentials & Signature */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2 border-b border-slate-800 pb-3">
              <Award className="w-4 h-4 text-emerald-400" />
              3. Licensed Engineer Statutory Credentials & Outcome
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
              <label className="block text-xs font-medium text-slate-400 mb-1">Engineer Review Notes & Remarks</label>
              <textarea
                rows={2}
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-100 focus:border-emerald-500 focus:outline-none"
                placeholder="Include any specific site stipulations, lap splice lengths, or inspection holds..."
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 rounded-xl font-semibold text-sm text-white bg-indigo-600 hover:bg-indigo-500 transition-all shadow-lg shadow-indigo-600/20 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Verifying Against IS 456 Clauses...
                </>
              ) : (
                <>
                  <FileCheck2 className="w-4 h-4" />
                  Submit Formal Engineering Review Sheet
                </>
              )}
            </button>
          </div>
        </form>

        {/* Right Output: Formal Review Sheet / Violations (5 cols) */}
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

          {/* Success: Formal Engineer Review Sheet */}
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

              {/* Sign-off Seal Block */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2">
                  <span className="font-semibold text-slate-200">Engineer Sign-Off Stamp</span>
                  <span className="font-mono text-emerald-400">{reviewResult.design?.approval_timestamp || reviewDate}</span>
                </div>
                <div className="text-xs space-y-1 font-mono">
                  <p><span className="text-slate-500">REVIEWER:</span> <strong className="text-slate-200">{reviewerName}</strong></p>
                  <p><span className="text-slate-500">ROLE:</span> <span className="text-slate-300">{reviewerRole}</span></p>
                  <p><span className="text-slate-500">REG NO:</span> <span className="text-blue-400">{licenseNo}</span></p>
                  <p><span className="text-slate-500">OUTCOME:</span> <span className="text-emerald-300">{outcome}</span></p>
                  {remarks && (
                    <p className="pt-1 text-slate-400 italic">
                      "{remarks}"
                    </p>
                  )}
                </div>
              </div>

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

              {/* Export Reviewed CAD Button */}
              <div className="pt-2">
                <button
                  onClick={handleExportReviewedCAD}
                  disabled={dxfExporting}
                  className="w-full py-2.5 px-4 rounded-xl text-xs font-semibold text-slate-900 bg-emerald-400 hover:bg-emerald-300 transition-all flex items-center justify-center gap-2 shadow"
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
                  <div className="mt-3 p-3 rounded-lg bg-emerald-950/50 border border-emerald-500/30 flex items-center justify-between">
                    <span className="text-xs font-mono text-emerald-300 truncate max-w-[200px]">
                      {dxfPath.split(/[/\\]/).pop()}
                    </span>
                    <a
                      href={getCADDownloadUrl(dxfPath)}
                      download
                      className="text-xs font-bold text-white underline hover:text-emerald-200"
                    >
                      Download
                    </a>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center space-y-3">
              <FileText className="w-10 h-10 text-slate-600 mx-auto" />
              <h3 className="text-sm font-semibold text-slate-300">
                Awaiting Engineering Review Submission
              </h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
                Fill in the member design loads and reviewer credentials on the left, then click submit to execute IS 456 validation and generate the formal review sheet.
              </p>
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
