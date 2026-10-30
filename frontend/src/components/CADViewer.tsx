import React, { useState } from 'react';
import { 
  Download, 
  Layers, 
  AlertTriangle, 
  FileCode, 
  ExternalLink, 
  CheckCircle2, 
  Loader2, 
  Compass, 
  Grid, 
  Square,
  Columns
} from 'lucide-react';
import { 
  exportBeamDXF, 
  exportColumnDXF, 
  exportSlabDXF, 
  exportFootingDXF, 
  getCADDownloadUrl 
} from '../services/api';
import type { CADExportResponse } from '../types/api';

interface CADViewerProps {
  onNavigateToStudio?: (element: 'beam' | 'column' | 'slab' | 'footing') => void;
}

export const CADViewer: React.FC<CADViewerProps> = ({ onNavigateToStudio }) => {
  const [selectedMember, setSelectedMember] = useState<'beam' | 'column' | 'slab' | 'footing'>('beam');
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastExport, setLastExport] = useState<CADExportResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Quick CAD generation handler with standard IS 456 safe defaults
  const handleQuickExport = async (memberType: 'beam' | 'column' | 'slab' | 'footing') => {
    setIsGenerating(true);
    setErrorMsg(null);
    try {
      let res: CADExportResponse;
      if (memberType === 'beam') {
        res = await exportBeamDXF({
          span_m: 5.0,
          dead_load_kN_per_m: 15.0,
          live_load_kN_per_m: 12.0,
          fck: 25,
          fy: 500,
          exposure: 'Moderate',
          output_filename: `beam_5m_${Date.now().toString().slice(-4)}.dxf`,
        });
      } else if (memberType === 'column') {
        res = await exportColumnDXF({
          axial_load_kN: 1200,
          length_m: 3.2,
          b_mm: 400,
          D_mm: 450,
          fck: 25,
          fy: 500,
          exposure: 'Moderate',
          output_filename: `column_400x450_${Date.now().toString().slice(-4)}.dxf`,
        });
      } else if (memberType === 'slab') {
        res = await exportSlabDXF({
          lx_m: 4.0,
          ly_m: 5.5,
          live_load_kN_m2: 3.0,
          floor_finish_kN_m2: 1.0,
          support_width_mm: 230,
          fck: 25,
          fy: 500,
          exposure: 'Moderate',
          support_condition: 'simply_supported',
          output_filename: `slab_4x5.5_${Date.now().toString().slice(-4)}.dxf`,
        });
      } else {
        res = await exportFootingDXF({
          axial_load_kN: 1200,
          sbc_kN_m2: 200,
          col_b_mm: 300,
          col_D_mm: 450,
          fck: 25,
          fy: 500,
          output_filename: `footing_1200kN_${Date.now().toString().slice(-4)}.dxf`,
        });
      }
      setLastExport(res);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to export DXF';
      setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setIsGenerating(false);
    }
  };

  const cadMemberDetails = {
    beam: {
      title: 'RC Beam Longitudinal & Cross Section',
      code: 'IS 456:2000 Cl. 26.5.1 & Table 19',
      dimensions: '230 mm × 450 mm (5.0 m Span)',
      rebar: 'Bottom: 3-T20 | Top: 2-T12 Hanger | 2L-T8 Stirrups @ 150mm c/c',
      layers: [
        { name: 'CONCRETE_OUTLINE', color: '#60A5FA', desc: 'Beam outline (0.50mm line weight)' },
        { name: 'REBAR_MAIN', color: '#F87171', desc: 'Bottom tension steel & top hanger bars' },
        { name: 'STIRRUPS', color: '#FBBF24', desc: '2-legged shear stirrups with 135° seismic hooks' },
        { name: 'DIMENSIONS', color: '#34D399', desc: 'Span, depth, cover, and stirrup spacing tags' },
        { name: 'DRAFT_WATERMARK', color: '#EF4444', desc: 'STATUS: DRAFT - NOT FOR CONSTRUCTION' }
      ]
    },
    column: {
      title: 'Short Column Section & Tie Elevation',
      code: 'IS 456:2000 Cl. 39.3 & Cl. 26.5.3',
      dimensions: '300 mm × 450 mm (3.2 m Unbraced Height)',
      rebar: 'Longitudinal: 6-T20 (1.4% Pt) | Lateral: 8mm Ties @ 200mm c/c',
      layers: [
        { name: 'CONCRETE_OUTLINE', color: '#60A5FA', desc: 'Column rect border (40mm clear cover)' },
        { name: 'REBAR_LONGITUDINAL', color: '#F87171', desc: 'Vertical load-bearing rebar arrangement' },
        { name: 'TIES_LATERAL', color: '#FBBF24', desc: 'Perimeter link and internal diamond/cross tie' },
        { name: 'DIMENSIONS', color: '#34D399', desc: 'Column b x D dimensions and pitch' },
        { name: 'DRAFT_WATERMARK', color: '#EF4444', desc: 'STATUS: DRAFT - NOT FOR CONSTRUCTION' }
      ]
    },
    slab: {
      title: 'Two-Way Slab Mesh & Edge Detailing',
      code: 'IS 456:2000 Cl. 24 & Annex D',
      dimensions: '4.0 m × 5.5 m (Thickness D = 140 mm)',
      rebar: 'Short Span: T10 @ 150mm c/c | Long Span: T8 @ 180mm c/c',
      layers: [
        { name: 'SLAB_OUTLINE', color: '#60A5FA', desc: 'Panel boundary and supporting wall lines' },
        { name: 'MAIN_BARS', color: '#F87171', desc: 'Bottom flexural bars along short span lx' },
        { name: 'DISTRIBUTION_BARS', color: '#FBBF24', desc: 'Secondary reinforcement along long span ly' },
        { name: 'DIMENSIONS', color: '#34D399', desc: 'Grid spacing, clear cover, and slab thickness' },
        { name: 'DRAFT_WATERMARK', color: '#EF4444', desc: 'STATUS: DRAFT - NOT FOR CONSTRUCTION' }
      ]
    },
    footing: {
      title: 'Isolated Spread Footing Plan & Section',
      code: 'IS 456:2000 Cl. 34 (Bearing & Punching Shear)',
      dimensions: '2.45 m × 2.45 m × 0.50 m Depth',
      rebar: 'Bottom Mat: T12 @ 150mm c/c both ways | Column Dowels: 6-T20',
      layers: [
        { name: 'FOOTING_CONCRETE', color: '#60A5FA', desc: 'Pad footing geometry with 50mm lean mud mat' },
        { name: 'COLUMN_STUB', color: '#94A3B8', desc: 'Column pedestal position & 50mm cover' },
        { name: 'MESH_X_Y', color: '#F87171', desc: 'Biaxial bottom reinforcement mat' },
        { name: 'DOWELS', color: '#FBBF24', desc: 'Starter dowels with 90° bend into base' },
        { name: 'DRAFT_WATERMARK', color: '#EF4444', desc: 'STATUS: DRAFT - NOT FOR CONSTRUCTION' }
      ]
    }
  };

  const current = cadMemberDetails[selectedMember];

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-3">
              <Layers className="w-3.5 h-3.5" />
              CAD Generator Engine (ezdxf R2010/R2018)
            </div>
            <h1 className="text-2xl font-bold text-slate-100">
              Autonomous 2D CAD Blueprints & DXF Export
            </h1>
            <p className="text-sm text-slate-400 mt-1 max-w-2xl">
              Generates production-grade AutoCAD drawings directly from deterministic IS 456 calculation models.
              Compatible with AutoCAD, LibreCAD, BricsCAD, and DWG TrueView.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => handleQuickExport(selectedMember)}
              disabled={isGenerating}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm text-white bg-blue-600 hover:bg-blue-500 transition-all shadow-lg shadow-blue-600/20 disabled:opacity-50"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating DXF...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Generate {selectedMember.toUpperCase()} DXF
                </>
              )}
            </button>
          </div>
        </div>

        {/* Member Selector Tabs */}
        <div className="flex gap-2 mt-6 border-b border-slate-800 pb-2">
          {[
            { id: 'beam', label: 'RC Beam DXF', icon: Compass },
            { id: 'column', label: 'RC Column DXF', icon: Columns },
            { id: 'slab', label: 'RC Slab DXF', icon: Grid },
            { id: 'footing', label: 'Footing DXF', icon: Square },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = selectedMember === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setSelectedMember(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  active
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Mandatory Safety Notice */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-5 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-amber-500/20 pb-3 mb-3">
          <div className="flex items-center gap-2 text-amber-300 font-bold text-xs uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span>AutoCAD Watermark Rule (Strict Statutory Safety Guardrail)</span>
          </div>
          <span className="inline-flex items-center px-3 py-1 rounded-md text-xs font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 whitespace-nowrap self-start sm:self-auto">
            STATUS: DRAFT - NOT FOR CONSTRUCTION
          </span>
        </div>
        <p className="text-xs text-amber-200/90 leading-relaxed">
          All CAD output files generated by this pipeline automatically include an indelible text entity stamped on layer{' '}
          <code className="text-amber-100 font-mono bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-500/30">
            DRAFT_WATERMARK
          </code>
          . This warning cannot be stripped or bypassed by automated routines. Only an authorized human licensed engineer holding a valid statutory license can issue final construction blueprints.
        </p>
      </div>

      {/* Export Result Notification Banner if exists */}
      {lastExport && (
        <div className="bg-emerald-950/40 border border-emerald-500/30 rounded-xl p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-emerald-200">
                DXF Successfully Generated: {lastExport.dxf_path.split(/[/\\]/).pop()}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                Saved on server at: <code className="text-emerald-300 font-mono">{lastExport.dxf_path}</code>
              </p>
            </div>
          </div>
          <a
            href={getCADDownloadUrl(lastExport.dxf_path)}
            download
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-slate-900 bg-emerald-400 hover:bg-emerald-300 transition-colors shadow"
          >
            <Download className="w-4 h-4" />
            Download .DXF
          </a>
        </div>
      )}

      {errorMsg && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-xs text-red-300">
          <strong>Export Error:</strong> {errorMsg}
        </div>
      )}

      {/* Main CAD Visualizer & Blueprint Schema */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Interactive AutoCAD Style Drawing Preview */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-100">{current.title}</h3>
                <span className="text-xs font-mono text-slate-400">{current.code}</span>
              </div>
              <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Units: Millimeters (mm)
              </span>
            </div>

            {/* Simulated AutoCAD Vector Canvas */}
            <div className="relative w-full h-80 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-center overflow-hidden p-6 select-none">
              {/* Subtle CAD Grid Background */}
              <div 
                className="absolute inset-0 opacity-15"
                style={{
                  backgroundImage: 'radial-gradient(#38bdf8 1px, transparent 1px)',
                  backgroundSize: '24px 24px'
                }}
              />

              {/* Diagonal Draft Watermark across Canvas */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
                <div className="transform -rotate-25 text-red-500/25 text-xl sm:text-2xl md:text-3xl font-mono font-black tracking-widest uppercase border-4 border-dashed border-red-500/25 px-6 py-3 rounded-lg text-center">
                  DRAFT - NOT FOR CONSTRUCTION
                </div>
              </div>

              {/* Dynamic SVG CAD Blueprint Rendering */}
              {selectedMember === 'beam' && (
                <svg className="w-full h-full max-h-64 z-10" viewBox="0 0 500 220" fill="none">
                  {/* Beam Outline */}
                  <rect x="50" y="60" width="400" height="90" stroke="#60A5FA" strokeWidth="2.5" fill="#1E293B" fillOpacity="0.4" />
                  {/* Top Hanger Rebar */}
                  <line x1="65" y1="75" x2="435" y2="75" stroke="#F87171" strokeWidth="2.5" strokeDasharray="none" />
                  {/* Bottom Main Tension Rebar */}
                  <line x1="65" y1="135" x2="435" y2="135" stroke="#EF4444" strokeWidth="4" />
                  {/* Shear Stirrups */}
                  {[90, 140, 190, 240, 290, 340, 390].map((x, i) => (
                    <line key={i} x1={x} y1="70" x2={x} y2="140" stroke="#FBBF24" strokeWidth="1.5" strokeDasharray="3 2" />
                  ))}
                  {/* Dimension Lines */}
                  <line x1="50" y1="170" x2="450" y2="170" stroke="#34D399" strokeWidth="1" />
                  <path d="M50 166 L50 174 M450 166 L450 174" stroke="#34D399" strokeWidth="1" />
                  <text x="230" y="185" fill="#34D399" fontSize="11" fontFamily="monospace" textAnchor="middle">SPAN = 5000 mm</text>
                  <text x="25" y="110" fill="#94A3B8" fontSize="10" fontFamily="monospace" textAnchor="middle" transform="rotate(-90 25 110)">D = 450 mm</text>
                  <text x="440" y="55" fill="#F87171" fontSize="10" fontFamily="monospace">2-T12 Top</text>
                  <text x="440" y="145" fill="#EF4444" fontSize="10" fontFamily="monospace">3-T20 Bot</text>
                </svg>
              )}

              {selectedMember === 'column' && (
                <svg className="w-full h-full max-h-64 z-10" viewBox="0 0 400 220" fill="none">
                  {/* Column Outer */}
                  <rect x="130" y="30" width="140" height="160" stroke="#60A5FA" strokeWidth="2.5" fill="#1E293B" fillOpacity="0.4" />
                  {/* Tie Link */}
                  <rect x="145" y="45" width="110" height="130" stroke="#FBBF24" strokeWidth="1.5" strokeDasharray="4 2" />
                  {/* 6 Rebar Circles */}
                  <circle cx="155" cy="55" r="7" fill="#EF4444" stroke="#fff" strokeWidth="1" />
                  <circle cx="200" cy="55" r="7" fill="#EF4444" stroke="#fff" strokeWidth="1" />
                  <circle cx="245" cy="55" r="7" fill="#EF4444" stroke="#fff" strokeWidth="1" />
                  <circle cx="155" cy="165" r="7" fill="#EF4444" stroke="#fff" strokeWidth="1" />
                  <circle cx="200" cy="165" r="7" fill="#EF4444" stroke="#fff" strokeWidth="1" />
                  <circle cx="245" cy="165" r="7" fill="#EF4444" stroke="#fff" strokeWidth="1" />
                  {/* Dimensions */}
                  <text x="200" y="20" fill="#34D399" fontSize="11" fontFamily="monospace" textAnchor="middle">b = 300 mm</text>
                  <text x="115" y="115" fill="#34D399" fontSize="11" fontFamily="monospace" textAnchor="middle" transform="rotate(-90 115 115)">D = 450 mm</text>
                  <text x="280" y="115" fill="#FBBF24" fontSize="10" fontFamily="monospace">8mm Ties @ 200 c/c</text>
                </svg>
              )}

              {selectedMember === 'slab' && (
                <svg className="w-full h-full max-h-64 z-10" viewBox="0 0 450 220" fill="none">
                  <rect x="75" y="30" width="300" height="150" stroke="#60A5FA" strokeWidth="2.5" fill="#1E293B" fillOpacity="0.4" />
                  {/* Main Bars (vertical / short span) */}
                  {[105, 145, 185, 225, 265, 305, 345].map((x, i) => (
                    <line key={i} x1={x} y1="40" x2={x} y2="170" stroke="#EF4444" strokeWidth="1.5" />
                  ))}
                  {/* Distribution Bars (horizontal / long span) */}
                  {[55, 80, 105, 130, 155].map((y, i) => (
                    <line key={i} x1="85" y1={y} x2="365" y2={y} stroke="#FBBF24" strokeWidth="1" strokeDasharray="3 2" />
                  ))}
                  <text x="225" y="20" fill="#34D399" fontSize="11" fontFamily="monospace" textAnchor="middle">Ly = 5500 mm</text>
                  <text x="55" y="110" fill="#34D399" fontSize="11" fontFamily="monospace" textAnchor="middle" transform="rotate(-90 55 110)">Lx = 4000 mm</text>
                  <text x="225" y="195" fill="#94A3B8" fontSize="10" fontFamily="monospace" textAnchor="middle">Thickness D = 140 mm</text>
                </svg>
              )}

              {selectedMember === 'footing' && (
                <svg className="w-full h-full max-h-64 z-10" viewBox="0 0 420 220" fill="none">
                  {/* Footing base */}
                  <rect x="70" y="50" width="280" height="120" stroke="#60A5FA" strokeWidth="2.5" fill="#1E293B" fillOpacity="0.4" />
                  {/* Column Pedestal */}
                  <rect x="180" y="15" width="60" height="35" stroke="#94A3B8" strokeWidth="2" strokeDasharray="3 2" />
                  {/* Dowels */}
                  <line x1="195" y1="15" x2="195" y2="140" stroke="#FBBF24" strokeWidth="2" />
                  <line x1="195" y1="140" x2="160" y2="140" stroke="#FBBF24" strokeWidth="2" />
                  <line x1="225" y1="15" x2="225" y2="140" stroke="#FBBF24" strokeWidth="2" />
                  <line x1="225" y1="140" x2="260" y2="140" stroke="#FBBF24" strokeWidth="2" />
                  {/* Bottom Mesh */}
                  <line x1="85" y1="150" x2="335" y2="150" stroke="#EF4444" strokeWidth="3" />
                  <text x="210" y="195" fill="#34D399" fontSize="11" fontFamily="monospace" textAnchor="middle">B = 2450 mm (Square Footing)</text>
                  <text x="45" y="115" fill="#34D399" fontSize="10" fontFamily="monospace" textAnchor="middle" transform="rotate(-90 45 115)">Depth = 500 mm</text>
                </svg>
              )}
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <span>Engineering Standard: {current.code}</span>
            {onNavigateToStudio && (
              <button
                onClick={() => onNavigateToStudio(selectedMember)}
                className="inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300 font-medium"
              >
                Customize parameters in Member Studio
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Right 1 Col: AutoCAD Layer Hierarchy & File Specifications */}
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2 mb-3">
              <Layers className="w-4 h-4 text-blue-400" />
              AutoCAD Layer Structure
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Layers follow standard AIA CAD and Indian CPWD detailing guidelines:
            </p>

            <div className="space-y-2.5">
              {current.layers.map((layer, idx) => (
                <div key={idx} className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-3 h-3 rounded-full border border-slate-700"
                        style={{ backgroundColor: layer.color }}
                      />
                      <span className="font-mono text-xs font-semibold text-slate-200">
                        {layer.name}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 pl-5">{layer.desc}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2 mb-2">
              <FileCode className="w-4 h-4 text-emerald-400" />
              Direct File Integration
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed mb-3">
              Generated files are output as ASCII DXF format. You can reference them via XREF or open them directly in any standard CAD viewer.
            </p>
            <div className="p-3 rounded-lg bg-slate-950 font-mono text-xs text-slate-300 border border-slate-800 space-y-1">
              <div><span className="text-slate-500">FORMAT:</span> AutoCAD DXF R2010</div>
              <div><span className="text-slate-500">UNITS:</span> Millimeters</div>
              <div><span className="text-slate-500">ENDPOINT:</span> GET /v1/cad/download/:name</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
