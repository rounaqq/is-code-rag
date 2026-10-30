import React, { useState } from 'react';
import {
  Layers,
  Search,
  ShieldCheck,
  AlertTriangle,
  Cpu,
  BookOpen,
  ArrowRight,
  Database,
  CheckCircle,
  FileCode,
  Compass,
  FileCheck2,
  Columns,
  Grid,
  Square
} from 'lucide-react';

interface DashboardProps {
  onNavigate: (tab: string) => void;
}

export const DashboardOverview: React.FC<DashboardProps> = ({ onNavigate }) => {
  const [heroView, setHeroView] = useState<'blueprint' | 'pipeline'>('blueprint');

  return (
    <div className="space-y-6">
      {/* 1. Hero Section with Interactive CAD Blueprint Visual */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 lg:p-8 shadow-xl relative overflow-hidden">
        {/* Subtle radial glow */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center relative z-10">
          {/* Left Hero Description (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
              <span>Decoupled Engineering AI Architecture</span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-100 leading-tight">
              Structural IS Code RAG &amp; <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-300 to-sky-400">
                Autonomous 2D CAD Drafting
              </span>
            </h1>

            <p className="text-sm text-slate-300 leading-relaxed max-w-xl">
              Engineered to minimize hallucination risk through a decoupled architecture: open-book legal clause retrieval across 5 Indian Standards, deterministic closed-form IS 456 calculations, and automated AutoCAD 2D drafting with clause citations.
            </p>

            {/* Quick Action Buttons */}
            <div className="flex flex-wrap gap-3 pt-2">
              <button
                onClick={() => onNavigate('design')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-xs text-white bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-600/20 transition-all duration-150"
              >
                <Layers className="w-4 h-4" />
                <span>Launch Design Studio</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>

              <button
                onClick={() => onNavigate('cad')}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-xs text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-all"
              >
                <FileCode className="w-4 h-4 text-emerald-400" />
                <span>CAD Blueprints</span>
              </button>

              <button
                onClick={() => onNavigate('rag')}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-xs text-slate-300 hover:text-white bg-slate-950/60 hover:bg-slate-800 border border-slate-800 transition-all"
              >
                <Search className="w-4 h-4 text-amber-400" />
                <span>IS Code Search</span>
              </button>
            </div>

            {/* Ingested Standards Badges */}
            <div className="pt-2 flex flex-wrap items-center gap-2 text-[11px] font-mono text-slate-400">
              <span className="text-slate-500 font-sans font-semibold">Active Codes:</span>
              <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-blue-300 font-semibold">IS 456:2000</span>
              <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-indigo-300 font-semibold">IS 13920:2016</span>
              <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-amber-300 font-semibold">IS 1893:2016</span>
              <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300 font-semibold">IS 800:2007</span>
              <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-teal-300 font-semibold">IS 875</span>
            </div>
          </div>

          {/* Right Hero CAD Blueprint Visual (5 cols) */}
          <div className="lg:col-span-5">
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 shadow-2xl relative overflow-hidden">
              {/* Header with Visual Mode Switcher */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-800 text-xs mb-3">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="font-mono text-slate-300 font-semibold text-[11px]">
                    {heroView === 'blueprint' ? '2D CAD Vector Elevation (mm)' : 'Load Path Decoupled Flow'}
                  </span>
                </div>
                <div className="flex rounded-lg bg-slate-900 border border-slate-800 p-0.5 text-[10px] font-medium">
                  <button
                    onClick={() => setHeroView('blueprint')}
                    className={`px-2 py-1 rounded transition ${
                      heroView === 'blueprint' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    CAD Elevation
                  </button>
                  <button
                    onClick={() => setHeroView('pipeline')}
                    className={`px-2 py-1 rounded transition ${
                      heroView === 'pipeline' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Load Pipeline
                  </button>
                </div>
              </div>

              {/* View 1: Meaningful 2D CAD Blueprint Visual */}
              {heroView === 'blueprint' ? (
                <div className="relative w-full h-56 bg-slate-950/90 rounded-lg border border-slate-800/80 flex items-center justify-center overflow-hidden p-2 select-none">
                  {/* Subtle Blueprint Grid Background */}
                  <div
                    className="absolute inset-0 opacity-15"
                    style={{
                      backgroundImage: 'radial-gradient(#38bdf8 1px, transparent 1px)',
                      backgroundSize: '18px 18px',
                    }}
                  />

                  {/* Diagonal AutoCAD Draft Watermark Entity */}
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
                    <div className="transform -rotate-15 text-red-500/25 text-base sm:text-lg font-mono font-black tracking-wider uppercase border-2 border-dashed border-red-500/30 px-3 py-1.5 rounded text-center">
                      STATUS: DRAFT - NOT FOR CONSTRUCTION
                    </div>
                  </div>

                  {/* SVG Structural Frame Elevation (Column + Beam + Stirrups) */}
                  <svg className="w-full h-full z-10" viewBox="0 0 380 180" fill="none">
                    {/* Grid Centerline */}
                    <line x1="20" y1="90" x2="360" y2="90" stroke="#475569" strokeWidth="0.8" strokeDasharray="6 3 1 3" />
                    <line x1="120" y1="10" x2="120" y2="170" stroke="#475569" strokeWidth="0.8" strokeDasharray="6 3 1 3" />

                    {/* Column Concrete Outline */}
                    <rect x="95" y="15" width="50" height="150" stroke="#60A5FA" strokeWidth="2" fill="#1E293B" fillOpacity="0.5" />
                    {/* Beam Concrete Outline spanning right */}
                    <rect x="145" y="65" width="215" height="50" stroke="#60A5FA" strokeWidth="2" fill="#1E293B" fillOpacity="0.5" />

                    {/* Beam Main Longitudinal Steel: Top 2-T12 */}
                    <line x1="105" y1="73" x2="350" y2="73" stroke="#F87171" strokeWidth="2" />
                    {/* Beam Main Longitudinal Steel: Bottom 3-T20 */}
                    <line x1="105" y1="107" x2="350" y2="107" stroke="#EF4444" strokeWidth="3" />

                    {/* Beam Shear Stirrups (2L-T8 @ 150 c/c) */}
                    {[165, 195, 225, 255, 285, 315, 345].map((x, idx) => (
                      <line key={idx} x1={x} y1="70" x2={x} y2="110" stroke="#FBBF24" strokeWidth="1.2" strokeDasharray="2 1" />
                    ))}

                    {/* Column Longitudinal Bars */}
                    <line x1="103" y1="18" x2="103" y2="162" stroke="#EF4444" strokeWidth="2.5" />
                    <line x1="137" y1="18" x2="137" y2="162" stroke="#EF4444" strokeWidth="2.5" />
                    {/* Column Ties */}
                    {[25, 45, 135, 155].map((y, idx) => (
                      <line key={idx} x1="98" y1={y} x2="142" y2={y} stroke="#FBBF24" strokeWidth="1" />
                    ))}

                    {/* Dimension Annotations */}
                    <text x="250" y="58" fill="#34D399" fontSize="8" fontFamily="monospace" textAnchor="middle">SPAN L = 5000 mm</text>
                    <text x="250" y="125" fill="#EF4444" fontSize="8" fontFamily="monospace" textAnchor="middle">3-T20 BOT | 2L-T8@150</text>
                    <text x="120" y="175" fill="#60A5FA" fontSize="8" fontFamily="monospace" textAnchor="middle">COL 300x450</text>
                  </svg>
                </div>
              ) : (
                /* View 2: Load Path Decoupled Flow */
                <div className="h-56 bg-slate-950/90 rounded-lg border border-slate-800/80 p-3 flex flex-col justify-between text-xs font-mono">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-300">1. Open-Book Retrieval</span>
                      <span className="text-indigo-400 font-bold">Qdrant + BM25</span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-300">2. Deterministic Math</span>
                      <span className="text-emerald-400 font-bold">IS 456:2000 Cl. 38</span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-300">3. AutoCAD 2D Drafting</span>
                      <span className="text-blue-400 font-bold">ezdxf R2010 Engine</span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-300">4. Human Sign-Off</span>
                      <span className="text-amber-400 font-bold">Statutory Review</span>
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-500 text-center">
                    Decoupled architecture: AI retrieves clauses, pure Python evaluates equations.
                  </div>
                </div>
              )}

              {/* Layer Legend Footer */}
              <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-blue-400" /> CONCRETE
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-400" /> MAIN REBAR
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-amber-400" /> STIRRUPS
                </span>
                <span className="text-slate-500">AutoCAD R2010</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Mandatory Statutory Safety Guardrail (No overlapping or awkward line wrapping) */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-5 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-amber-500/20 pb-3 mb-3">
          <div className="flex items-center gap-2 text-amber-300 font-bold text-xs uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span>Mandatory Statutory Engineering Guardrail</span>
          </div>
          <span className="inline-flex items-center px-3 py-1 rounded-md text-xs font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 whitespace-nowrap self-start sm:self-auto">
            STATUS: DRAFT - NOT FOR CONSTRUCTION
          </span>
        </div>

        <p className="text-xs text-amber-200/90 leading-relaxed">
          All computer-generated schedules, member dimensions, and 2D CAD files carry an immutable text watermark on layer{' '}
          <code className="font-mono font-semibold bg-amber-950/60 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/30">
            DRAFT_WATERMARK
          </code>
          . In accordance with the National Building Code of India (NBC 2016) and municipal bylaws, automated designs are preliminary computational aids. Blueprints must be reviewed, verified, and stamped by an authorized licensed structural engineer before construction.
        </p>
      </div>

      {/* 3. 4 Key Pillars Metrics Grid (Verified Against Codebase & Full Pytest Suite) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1 */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg hover:border-slate-700 transition space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span className="uppercase tracking-wider">Standards Ingested</span>
            <BookOpen className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-black text-slate-100 font-mono">
            5 Standards
          </div>
          <p className="text-xs text-slate-400">
            IS 456, IS 13920, IS 1893, IS 800, IS 875
          </p>
          <div className="text-[10px] text-blue-400 font-mono pt-1">
            ✓ Multi-code hybrid retrieval
          </div>
        </div>

        {/* Metric 2 */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg hover:border-slate-700 transition space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span className="uppercase tracking-wider">Official Corpus</span>
            <Database className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-black text-slate-100 font-mono">
            28 Documents
          </div>
          <p className="text-xs text-slate-400">
            13 amendments &amp; 2 errata slips
          </p>
          <div className="text-[10px] text-emerald-400 font-mono pt-1">
            ✓ SHA-256 integrity verified
          </div>
        </div>

        {/* Metric 3 */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg hover:border-slate-700 transition space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span className="uppercase tracking-wider">Indexed Clauses</span>
            <Cpu className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-black text-slate-100 font-mono">
            1,535 Chunks
          </div>
          <p className="text-xs text-slate-400">
            Dense semantic vectors &amp; BM25
          </p>
          <div className="text-[10px] text-indigo-400 font-mono pt-1">
            ✓ BGE Cross-Encoder reranking
          </div>
        </div>

        {/* Metric 4 */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg hover:border-slate-700 transition space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span className="uppercase tracking-wider">Automated Tests</span>
            <CheckCircle className="w-4 h-4 text-teal-400" />
          </div>
          <div className="text-2xl font-black text-slate-100 font-mono">
            296 Passed
          </div>
          <p className="text-xs text-slate-400">
            Full regression &amp; sizing suite
          </p>
          <div className="text-[10px] text-teal-400 font-mono pt-1">
            ✓ 100% green test suite
          </div>
        </div>
      </div>

      {/* 4. The 4 Structural Members Workflow (Gravity Load Path) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
          <div>
            <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Compass className="w-4 h-4 text-blue-400" />
              Building Gravity Load Path &amp; Member Sizing Engines
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Every structural component is calculated via closed-form IS 456 formulas and detailed in AutoCAD .DXF format.
            </p>
          </div>
          <button
            onClick={() => onNavigate('design')}
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 inline-flex items-center gap-1 self-start sm:self-auto"
          >
            Open All in Studio <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Floor Slabs */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 hover:border-blue-500/40 hover:shadow-lg transition-all flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-200 text-sm flex items-center gap-1.5">
                  <Grid className="w-4 h-4 text-blue-400" />
                  1. Floor Slabs
                </span>
                <span className="text-[10px] bg-blue-500/10 text-blue-400 font-semibold px-2 py-0.5 rounded border border-blue-500/20 font-mono">
                  Cl. 24
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                One-way &amp; two-way slab panels, effective depth (d), deflection control, and bottom flexural mesh.
              </p>
            </div>
            <button
              onClick={() => onNavigate('slab')}
              className="text-xs font-semibold text-blue-400 hover:text-blue-300 inline-flex items-center gap-1 pt-1"
            >
              Size Slabs <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          {/* 2. Floor Beams */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 hover:border-blue-500/40 hover:shadow-lg transition-all flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-200 text-sm flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-emerald-400" />
                  2. Floor Beams
                </span>
                <span className="text-[10px] bg-emerald-500/10 text-emerald-400 font-semibold px-2 py-0.5 rounded border border-emerald-500/20 font-mono">
                  Cl. 26.5.1
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Tension rebar (Ast), top hanger steel, Table 19 shear stirrup spacing, and bar curtailment rules.
              </p>
            </div>
            <button
              onClick={() => onNavigate('beam')}
              className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 inline-flex items-center gap-1 pt-1"
            >
              Size Beams <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          {/* 3. Columns */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 hover:border-blue-500/40 hover:shadow-lg transition-all flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-200 text-sm flex items-center gap-1.5">
                  <Columns className="w-4 h-4 text-amber-400" />
                  3. Columns
                </span>
                <span className="text-[10px] bg-amber-500/10 text-amber-400 font-semibold px-2 py-0.5 rounded border border-amber-500/20 font-mono">
                  Cl. 39.3
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Axial capacity (Pu), minimum eccentricity (0.05D), longitudinal rebar (0.8% - 4.0%), and lateral ties.
              </p>
            </div>
            <button
              onClick={() => onNavigate('column')}
              className="text-xs font-semibold text-amber-400 hover:text-amber-300 inline-flex items-center gap-1 pt-1"
            >
              Size Columns <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          {/* 4. Isolated Footings */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 hover:border-blue-500/40 hover:shadow-lg transition-all flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-200 text-sm flex items-center gap-1.5">
                  <Square className="w-4 h-4 text-indigo-400" />
                  4. Footings
                </span>
                <span className="text-[10px] bg-indigo-500/10 text-indigo-400 font-semibold px-2 py-0.5 rounded border border-indigo-500/20 font-mono">
                  Cl. 34
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Bearing area from SBC, one-way shear, two-way punching shear at d/2, and column starter dowels.
              </p>
            </div>
            <button
              onClick={() => onNavigate('footing')}
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1 pt-1"
            >
              Size Footings <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* 5. Production Observability & Governance Snapshot Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-semibold text-indigo-400">
              <FileCheck2 className="w-4 h-4" />
              <span>Licensed Engineer Review</span>
            </div>
            <h3 className="text-sm font-bold text-slate-100">
              Human-in-the-Loop Sign-Off Portal
            </h3>
            <p className="text-xs text-slate-400">
              Test manual parameter overrides verified by IS 456 rules and stamp candidate designs.
            </p>
          </div>
          <button
            onClick={() => onNavigate('review')}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 whitespace-nowrap shadow transition"
          >
            Review Portal
          </button>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
              <CheckCircle className="w-4 h-4" />
              <span>Production Telemetry</span>
            </div>
            <h3 className="text-sm font-bold text-slate-100">
              Observability &amp; Latency Metrics
            </h3>
            <p className="text-xs text-slate-400">
              Inspect p50/p95 latency percentiles, status codes, and top retrieved clauses in real time.
            </p>
          </div>
          <button
            onClick={() => onNavigate('observability')}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-900 bg-emerald-400 hover:bg-emerald-300 whitespace-nowrap shadow transition"
          >
            View Telemetry
          </button>
        </div>
      </div>
    </div>
  );
};
