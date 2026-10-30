import React, { useState } from 'react';
import {
  sizeBeam,
  exportBeamDXF,
  sizeColumn,
  exportColumnDXF,
  sizeSlab,
  exportSlabDXF,
  sizeFooting,
  exportFootingDXF,
  getCADDownloadUrl,
} from '../services/api';
import {
  Layers,
  Download,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Loader2,
  FileCode,
  Compass,
  Columns,
  Grid,
  Square,
  ShieldCheck,
} from 'lucide-react';

interface MemberStudioProps {
  initialMember?: 'beam' | 'column' | 'slab' | 'footing';
}

export const MemberStudio: React.FC<MemberStudioProps> = ({ initialMember = 'beam' }) => {
  const [activeMember, setActiveMember] = useState<'beam' | 'column' | 'slab' | 'footing'>(initialMember);

  React.useEffect(() => {
    if (initialMember) {
      setActiveMember(initialMember);
    }
  }, [initialMember]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExportingCAD, setIsExportingCAD] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Results State
  const [beamResult, setBeamResult] = useState<any | null>(null);
  const [columnResult, setColumnResult] = useState<any | null>(null);
  const [slabResult, setSlabResult] = useState<any | null>(null);
  const [footingResult, setFootingResult] = useState<any | null>(null);
  const [cadExport, setCadExport] = useState<any | null>(null);

  // Form States with Realistic Engineering Defaults
  const [beamForm, setBeamForm] = useState({
    span_m: 5.0,
    dead_load_kN_per_m: 18.0,
    live_load_kN_per_m: 12.0,
    fck: 25.0,
    fy: 500.0,
    exposure: 'Moderate',
  });

  const [columnForm, setColumnForm] = useState({
    axial_load_kN: 1200.0,
    length_m: 3.2,
    b_mm: 400,
    D_mm: 450,
    fck: 25.0,
    fy: 500.0,
    exposure: 'Moderate',
  });

  const [slabForm, setSlabForm] = useState({
    lx_m: 4.0,
    ly_m: 5.5,
    live_load_kN_m2: 3.0,
    floor_finish_kN_m2: 1.0,
    support_width_mm: 230,
    fck: 25.0,
    fy: 500.0,
    exposure: 'Moderate',
    support_condition: 'simply_supported',
  });

  const [footingForm, setFootingForm] = useState({
    axial_load_kN: 1200.0,
    sbc_kN_m2: 200.0,
    col_b_mm: 300,
    col_D_mm: 450,
    fck: 25.0,
    fy: 500.0,
  });

  // Calculate Handler
  const handleCalculate = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    setCadExport(null);

    try {
      if (activeMember === 'beam') {
        const res = await sizeBeam(beamForm);
        setBeamResult(res);
      } else if (activeMember === 'column') {
        const res = await sizeColumn(columnForm);
        setColumnResult(res);
      } else if (activeMember === 'slab') {
        const res = await sizeSlab(slabForm);
        setSlabResult(res);
      } else if (activeMember === 'footing') {
        const res = await sizeFooting(footingForm);
        setFootingResult(res);
      }
    } catch (err: any) {
      if (err.response?.status === 401) {
        setErrorMsg('Unauthorized (401): Valid X-API-Key is required. Please click "Configure API Key" to set your key.');
      } else {
        const msg = err.response?.data?.detail || err.message || 'Calculation failed. Please verify inputs.';
        setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Export CAD Handler
  const handleExportCAD = async () => {
    setIsExportingCAD(true);
    setErrorMsg(null);

    try {
      let res;
      if (activeMember === 'beam') {
        res = await exportBeamDXF({
          ...beamForm,
          output_filename: `beam_${beamForm.span_m}m_${Date.now().toString().slice(-4)}.dxf`,
        });
      } else if (activeMember === 'column') {
        res = await exportColumnDXF({
          ...columnForm,
          output_filename: `column_${columnForm.b_mm}x${columnForm.D_mm}_${Date.now().toString().slice(-4)}.dxf`,
        });
      } else if (activeMember === 'slab') {
        res = await exportSlabDXF({
          ...slabForm,
          output_filename: `slab_${slabForm.lx_m}x${slabForm.ly_m}_${Date.now().toString().slice(-4)}.dxf`,
        });
      } else if (activeMember === 'footing') {
        res = await exportFootingDXF({
          ...footingForm,
          output_filename: `footing_${footingForm.axial_load_kN}kN_${Date.now().toString().slice(-4)}.dxf`,
        });
      }
      setCadExport(res);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'CAD drafting failed.';
      setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setIsExportingCAD(false);
    }
  };

  const memberTabs = [
    { id: 'beam', label: 'RC Beam', code: 'IS 456 Cl. 26.5.1', icon: Layers },
    { id: 'column', label: 'RC Column', code: 'IS 456 Cl. 39.3', icon: Columns },
    { id: 'slab', label: 'RC Slab', code: 'IS 456 Cl. 24', icon: Grid },
    { id: 'footing', label: 'Footing', code: 'IS 456 Cl. 34', icon: Square },
  ];

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-2">
              <Compass className="w-3.5 h-3.5" />
              <span>IS 456:2000 Limit State Sizing</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-100">Structural Member Design Studio</h1>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl">
              Deterministic calculations for bending moment, effective depth, reinforcement schedules, and direct 2D AutoCAD .dxf export.
            </p>
          </div>

          {/* Member Switcher */}
          <div className="flex p-1 bg-slate-950 rounded-xl border border-slate-800 self-start md:self-auto gap-1">
            {memberTabs.map((m) => {
              const Icon = m.icon;
              const active = activeMember === m.id;
              return (
                <button
                  key={m.id}
                  onClick={() => {
                    setActiveMember(m.id as any);
                    setCadExport(null);
                  }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                    active
                      ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{m.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {errorMsg && (
        <div className="bg-rose-950/40 border border-rose-500/30 rounded-2xl p-4 text-rose-300 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs shadow-lg">
          <div className="flex items-start gap-3">
            <XCircle className="h-5 w-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <strong className="block text-rose-200 mb-0.5">Calculation Warning / Error:</strong>
              <span>{errorMsg}</span>
            </div>
          </div>
          {errorMsg.includes('401') && (
            <button
              onClick={() => window.dispatchEvent(new CustomEvent('open_api_key_modal'))}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-semibold hover:bg-amber-500/30 whitespace-nowrap self-start sm:self-auto transition shadow-sm"
            >
              Configure API Key
            </button>
          )}
        </div>
      )}

      {/* Main Grid: Form Left (5 cols), Results Right (7 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Form: 5 Columns */}
        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
              {activeMember} Parameters
            </h2>
            <span className="text-[11px] font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
              {memberTabs.find((t) => t.id === activeMember)?.code}
            </span>
          </div>

          {/* BEAM FORM */}
          {activeMember === 'beam' && (
            <div className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Clear Span (meters)</label>
                <input
                  type="number"
                  step="0.1"
                  min="1"
                  max="20"
                  value={beamForm.span_m}
                  onChange={(e) => setBeamForm({ ...beamForm, span_m: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Dead Load (kN/m)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    value={beamForm.dead_load_kN_per_m}
                    onChange={(e) => setBeamForm({ ...beamForm, dead_load_kN_per_m: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Live Load (kN/m)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    value={beamForm.live_load_kN_per_m}
                    onChange={(e) => setBeamForm({ ...beamForm, live_load_kN_per_m: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Concrete Grade (fck)</label>
                  <select
                    value={beamForm.fck}
                    onChange={(e) => setBeamForm({ ...beamForm, fck: parseFloat(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 focus:border-blue-500 focus:outline-none"
                  >
                    <option value={20}>M20 (20 N/mm²)</option>
                    <option value={25}>M25 (25 N/mm²)</option>
                    <option value={30}>M30 (30 N/mm²)</option>
                    <option value={35}>M35 (35 N/mm²)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Steel Grade (fy)</label>
                  <select
                    value={beamForm.fy}
                    onChange={(e) => setBeamForm({ ...beamForm, fy: parseFloat(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 focus:border-blue-500 focus:outline-none"
                  >
                    <option value={415}>Fe 415</option>
                    <option value={500}>Fe 500</option>
                    <option value={550}>Fe 550D</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Exposure Condition</label>
                <select
                  value={beamForm.exposure}
                  onChange={(e) => setBeamForm({ ...beamForm, exposure: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 focus:border-blue-500 focus:outline-none"
                >
                  <option value="Mild">Mild (20mm Cover)</option>
                  <option value="Moderate">Moderate (30mm Cover)</option>
                  <option value="Severe">Severe (45mm Cover)</option>
                </select>
              </div>
            </div>
          )}

          {/* COLUMN FORM */}
          {activeMember === 'column' && (
            <div className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Service Axial Load (kN)</label>
                <input
                  type="number"
                  step="50"
                  min="100"
                  value={columnForm.axial_load_kN}
                  onChange={(e) => setColumnForm({ ...columnForm, axial_load_kN: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Unsupported Height (meters)</label>
                <input
                  type="number"
                  step="0.1"
                  min="1"
                  max="10"
                  value={columnForm.length_m}
                  onChange={(e) => setColumnForm({ ...columnForm, length_m: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Width b (mm)</label>
                  <input
                    type="number"
                    step="25"
                    min="200"
                    value={columnForm.b_mm}
                    onChange={(e) => setColumnForm({ ...columnForm, b_mm: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Depth D (mm)</label>
                  <input
                    type="number"
                    step="25"
                    min="200"
                    value={columnForm.D_mm}
                    onChange={(e) => setColumnForm({ ...columnForm, D_mm: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          )}

          {/* SLAB FORM */}
          {activeMember === 'slab' && (
            <div className="space-y-3.5">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Shorter Span Lx (m)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="1"
                    value={slabForm.lx_m}
                    onChange={(e) => setSlabForm({ ...slabForm, lx_m: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Longer Span Ly (m)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="1"
                    value={slabForm.ly_m}
                    onChange={(e) => setSlabForm({ ...slabForm, ly_m: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Live Load (kN/m²)</label>
                <input
                  type="number"
                  step="0.5"
                  min="1"
                  value={slabForm.live_load_kN_m2}
                  onChange={(e) => setSlabForm({ ...slabForm, live_load_kN_m2: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>
          )}

          {/* FOOTING FORM */}
          {activeMember === 'footing' && (
            <div className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Column Axial Load (kN)</label>
                <input
                  type="number"
                  step="50"
                  min="100"
                  value={footingForm.axial_load_kN}
                  onChange={(e) => setFootingForm({ ...footingForm, axial_load_kN: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Safe Bearing Capacity SBC (kN/m²)</label>
                <input
                  type="number"
                  step="10"
                  min="50"
                  value={footingForm.sbc_kN_m2}
                  onChange={(e) => setFootingForm({ ...footingForm, sbc_kN_m2: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>
          )}

          {/* Action Button */}
          <div className="pt-2">
            <button
              onClick={handleCalculate}
              disabled={isLoading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:opacity-50 text-white font-semibold py-3 rounded-xl text-xs shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 transition"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Computing IS 456 Formulas...</span>
                </>
              ) : (
                <>
                  <Layers className="h-4 w-4" />
                  <span>Calculate IS 456 Sizing</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right Output: 7 Columns */}
        <div className="lg:col-span-7 space-y-4">
          {/* Default Empty State */}
          {!beamResult && !columnResult && !slabResult && !footingResult && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-10 text-center shadow-xl space-y-3">
              <Layers className="h-10 w-10 mx-auto text-slate-600" />
              <h3 className="font-bold text-slate-200 text-sm">Ready to Calculate</h3>
              <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
                Adjust the design loads and material grades on the left, then click Calculate to execute closed-form limit state sizing.
              </p>
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] bg-slate-950 text-slate-400 border border-slate-800 font-mono">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
                Pure Deterministic Calculations
              </div>
            </div>
          )}

          {/* Result Card for Beam */}
          {activeMember === 'beam' && beamResult && (() => {
            const beamData = beamResult.design || beamResult.design_dict || beamResult.sizing?.design_dict;
            const mainBarCount = beamData?.main_bar_count;
            const mainBarDia = beamData?.main_bar_dia_mm;
            const astProvided = beamData?.ast_provided_mm2 ?? (
              mainBarCount && mainBarDia
                ? Math.round(mainBarCount * (Math.PI / 4.0) * Math.pow(mainBarDia, 2))
                : undefined
            );
            const stirrupLegs = beamData?.stirrup_legs ?? 2;
            const stirrupDia = beamData?.stirrup_dia_mm;
            const stirrupSpacing = beamData?.stirrup_spacing_mm;
            const isVerified = beamResult.status === 'success' || beamResult.status === 'ok';

            return (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4 animate-in fade-in">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="font-bold text-slate-100 text-sm">RC Beam Sizing Results</h3>
                    <p className="text-xs text-slate-400 font-mono">IS 456:2000 Cl. 26.5.1 Flexure &amp; Shear</p>
                  </div>
                  {isVerified ? (
                    <span className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      <span>Verified</span>
                    </span>
                  ) : (
                    <span className="bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                      <span>Needs Review</span>
                    </span>
                  )}
                </div>

                {beamResult.reason && (
                  <div className="p-3 bg-red-950/40 border border-red-800/50 rounded-xl text-xs text-red-300 font-mono">
                    {beamResult.reason}
                  </div>
                )}

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono">
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Dimensions</span>
                    <div className="text-sm font-bold text-slate-100 mt-1">
                      {beamData?.b != null && beamData?.D != null ? `${beamData.b} × ${beamData.D} mm` : '—'}
                    </div>
                  </div>
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Bottom Steel (Ast)</span>
                    <div className="text-sm font-bold text-emerald-400 mt-1">
                      {mainBarCount != null && mainBarDia != null ? `${mainBarCount} - T${mainBarDia}` : '—'}
                    </div>
                    {astProvided != null && (
                      <span className="text-[10px] text-slate-400">
                        ({astProvided.toFixed(0)} mm²)
                      </span>
                    )}
                  </div>
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Shear Stirrups</span>
                    <div className="text-sm font-bold text-amber-400 mt-1">
                      {stirrupDia != null && stirrupSpacing != null ? `${stirrupLegs}L-T${stirrupDia} @ ${stirrupSpacing}mm` : '—'}
                    </div>
                  </div>
                </div>

                {/* Draft Watermark Badge */}
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 text-xs text-amber-200 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0" />
                  <span className="font-mono font-bold text-amber-300">
                    STATUS: DRAFT - NOT FOR CONSTRUCTION
                  </span>
                </div>

                {/* CAD Action */}
                <div className="pt-2 flex items-center justify-between gap-3">
                  <button
                    onClick={handleExportCAD}
                    disabled={isExportingCAD}
                    className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-100 text-xs font-semibold px-4 py-2.5 rounded-xl flex items-center gap-2 transition"
                  >
                    {isExportingCAD ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Drafting AutoCAD DXF...</span>
                      </>
                    ) : (
                      <>
                        <FileCode className="h-3.5 w-3.5 text-blue-400" />
                        <span>Generate 2D CAD Blueprint (.DXF)</span>
                      </>
                    )}
                  </button>

                  {cadExport && (
                    <a
                      href={getCADDownloadUrl(cadExport.dxf_path)}
                      download
                      className="bg-emerald-400 hover:bg-emerald-300 text-slate-900 text-xs font-bold px-4 py-2.5 rounded-xl flex items-center gap-1.5 shadow transition"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>Download DXF</span>
                    </a>
                  )}
                </div>
              </div>
            );
          })()}

          {/* Result Card for Column */}
          {activeMember === 'column' && columnResult && (() => {
            const colData = columnResult.design_dict || columnResult;
            const dims = columnResult.section_dimensions || colData.section_dimensions || (colData.width_mm && colData.depth_mm ? `${colData.width_mm}x${colData.depth_mm} mm` : '—');
            const rebarCallout = columnResult.rebar_selected?.callout || colData.rebar_selected?.callout;
            const tiesCallout = columnResult.lateral_ties?.callout || colData.lateral_ties?.callout;
            const isOk = columnResult.status === 'success' || columnResult.status === 'ok';

            return (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4 animate-in fade-in">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="font-bold text-slate-100 text-sm">Column Sizing Results</h3>
                    <p className="text-xs text-slate-400 font-mono">IS 456 Cl. 39.3 Short Axial Compression</p>
                  </div>
                  <span className={`border text-xs font-semibold px-2.5 py-1 rounded-full ${
                    isOk ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                  }`}>
                    {isOk ? 'OK' : 'Needs Review'}
                  </span>
                </div>

                {columnResult.reason && (
                  <div className="p-3 bg-amber-950/40 border border-amber-800/50 rounded-xl text-xs text-amber-200 font-mono">
                    <span className="font-bold block text-amber-300 mb-0.5">IS 456 Limitation Notice (Needs Review):</span>
                    <span>{columnResult.reason}</span>
                  </div>
                )}

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono">
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Section</span>
                    <div className="text-sm font-bold text-slate-100 mt-1">{dims}</div>
                  </div>
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Main Rebar</span>
                    <div className="text-sm font-bold text-emerald-400 mt-1">{rebarCallout || '—'}</div>
                  </div>
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Lateral Ties</span>
                    <div className="text-sm font-bold text-amber-400 mt-1">{tiesCallout || '—'}</div>
                  </div>
                </div>

                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 text-xs text-amber-200 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0" />
                  <span className="font-mono font-bold text-amber-300">STATUS: DRAFT - NOT FOR CONSTRUCTION</span>
                </div>

                <div className="pt-2 flex items-center justify-between gap-3">
                  <button
                    onClick={handleExportCAD}
                    disabled={isExportingCAD}
                    className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-100 text-xs font-semibold px-4 py-2.5 rounded-xl flex items-center gap-2 transition"
                  >
                    {isExportingCAD ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Drafting AutoCAD DXF...</span>
                      </>
                    ) : (
                      <>
                        <FileCode className="h-3.5 w-3.5 text-blue-400" />
                        <span>Generate Column CAD (.DXF)</span>
                      </>
                    )}
                  </button>

                  {cadExport && (
                    <a
                      href={getCADDownloadUrl(cadExport.dxf_path)}
                      download
                      className="bg-emerald-400 hover:bg-emerald-300 text-slate-900 text-xs font-bold px-4 py-2.5 rounded-xl flex items-center gap-1.5 shadow transition"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>Download DXF</span>
                    </a>
                  )}
                </div>
              </div>
            );
          })()}

          {/* Result Card for Slab */}
          {activeMember === 'slab' && slabResult && (() => {
            const slabData = slabResult.design_dict || slabResult;
            const geom = slabResult.geometry || slabData.geometry;
            const flex = slabResult.flexure || slabData.flexure;
            const slabType = slabResult.slab_type || slabData.classification?.slab_type || 'TWO_WAY';
            const depthD = geom?.overall_depth_D_mm ?? slabResult.thickness_D_mm;
            const mainSteel = flex?.main_rebar_x?.callout || slabResult.main_reinforcement;
            const transSteel = flex?.transverse_reinforcement?.rebar?.callout || flex?.transverse_reinforcement?.dist_rebar?.callout || slabResult.transverse_reinforcement;
            const isOk = slabResult.status === 'success' || slabResult.status === 'ok';

            return (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4 animate-in fade-in">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="font-bold text-slate-100 text-sm">Slab Sizing Results</h3>
                    <p className="text-xs text-slate-400 font-mono">Type: {String(slabType).toUpperCase()}</p>
                  </div>
                  <span className={`border text-xs font-semibold px-2.5 py-1 rounded-full ${
                    isOk ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                  }`}>
                    {isOk ? 'OK' : 'Needs Review'}
                  </span>
                </div>

                {slabResult.reason && (
                  <div className="p-3 bg-amber-950/40 border border-amber-800/50 rounded-xl text-xs text-amber-200 font-mono">
                    <span className="font-bold block text-amber-300 mb-0.5">IS 456 Limitation Notice (Needs Review):</span>
                    <span>{slabResult.reason}</span>
                  </div>
                )}

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono">
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Thickness (D)</span>
                    <div className="text-sm font-bold text-slate-100 mt-1">{depthD != null ? `${depthD} mm` : '—'}</div>
                  </div>
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Main Steel</span>
                    <div className="text-sm font-bold text-emerald-400 mt-1">{mainSteel || '—'}</div>
                  </div>
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Transverse Steel</span>
                    <div className="text-sm font-bold text-amber-400 mt-1">{transSteel || '—'}</div>
                  </div>
                </div>

                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 text-xs text-amber-200 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0" />
                  <span className="font-mono font-bold text-amber-300">STATUS: DRAFT - NOT FOR CONSTRUCTION</span>
                </div>

                <div className="pt-2 flex items-center justify-between gap-3">
                  <button
                    onClick={handleExportCAD}
                    disabled={isExportingCAD}
                    className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-100 text-xs font-semibold px-4 py-2.5 rounded-xl flex items-center gap-2 transition"
                  >
                    {isExportingCAD ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Drafting AutoCAD DXF...</span>
                      </>
                    ) : (
                      <>
                        <FileCode className="h-3.5 w-3.5 text-blue-400" />
                        <span>Generate Slab CAD (.DXF)</span>
                      </>
                    )}
                  </button>

                  {cadExport && (
                    <a
                      href={getCADDownloadUrl(cadExport.dxf_path)}
                      download
                      className="bg-emerald-400 hover:bg-emerald-300 text-slate-900 text-xs font-bold px-4 py-2.5 rounded-xl flex items-center gap-1.5 shadow transition"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>Download DXF</span>
                    </a>
                  )}
                </div>
              </div>
            );
          })()}

          {/* Result Card for Footing */}
          {activeMember === 'footing' && footingResult && (() => {
            const fData = footingResult.design_dict || footingResult;
            const geom = footingResult.geometry || fData.geometry;
            const flex = footingResult.flexure || fData.flexure;
            const bDim = geom?.B_mm;
            const lDim = geom?.L_mm;
            const planDims = bDim && lDim ? `${bDim} × ${lDim} mm` : footingResult.plan_dimensions;
            const totalDepthD = geom?.total_depth_D_mm ?? footingResult.thickness_D_mm;
            const rebarMesh = flex?.rebar_mesh?.callout || footingResult.reinforcement_both_ways;
            const isOk = footingResult.status === 'success' || footingResult.status === 'ok';

            return (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4 animate-in fade-in">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="font-bold text-slate-100 text-sm">Isolated Footing Results</h3>
                    <p className="text-xs text-slate-400 font-mono">IS 456 Cl. 34 Foundation Design</p>
                  </div>
                  <span className={`border text-xs font-semibold px-2.5 py-1 rounded-full ${
                    isOk ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                  }`}>
                    {isOk ? 'OK' : 'Needs Review'}
                  </span>
                </div>

                {footingResult.reason && (
                  <div className="p-3 bg-amber-950/40 border border-amber-800/50 rounded-xl text-xs text-amber-200 font-mono">
                    <span className="font-bold block text-amber-300 mb-0.5">IS 456 Limitation Notice (Needs Review):</span>
                    <span>{footingResult.reason}</span>
                  </div>
                )}

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono">
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Base Area (B x L)</span>
                    <div className="text-sm font-bold text-slate-100 mt-1">
                      {planDims || '—'}
                    </div>
                  </div>
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Depth (D)</span>
                    <div className="text-sm font-bold text-slate-100 mt-1">{totalDepthD != null ? `${totalDepthD} mm` : '—'}</div>
                  </div>
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Rebar Mesh</span>
                    <div className="text-sm font-bold text-emerald-400 mt-1">{rebarMesh || '—'}</div>
                  </div>
                </div>

                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 text-xs text-amber-200 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0" />
                  <span className="font-mono font-bold text-amber-300">STATUS: DRAFT - NOT FOR CONSTRUCTION</span>
                </div>

                <div className="pt-2 flex items-center justify-between gap-3">
                  <button
                    onClick={handleExportCAD}
                    disabled={isExportingCAD}
                    className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-100 text-xs font-semibold px-4 py-2.5 rounded-xl flex items-center gap-2 transition"
                  >
                    {isExportingCAD ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Drafting AutoCAD DXF...</span>
                      </>
                    ) : (
                      <>
                        <FileCode className="h-3.5 w-3.5 text-blue-400" />
                        <span>Generate Footing CAD (.DXF)</span>
                      </>
                    )}
                  </button>

                  {cadExport && (
                    <a
                      href={getCADDownloadUrl(cadExport.dxf_path)}
                      download
                      className="bg-emerald-400 hover:bg-emerald-300 text-slate-900 text-xs font-bold px-4 py-2.5 rounded-xl flex items-center gap-1.5 shadow transition"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>Download DXF</span>
                    </a>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
};
