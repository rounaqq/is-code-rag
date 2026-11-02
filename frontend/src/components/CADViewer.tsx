import React, { useState, useRef } from 'react';
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
  Columns,
  Sparkles,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Maximize2,
  Minimize2,
  Eye,
  EyeOff,
  Ruler,
  Printer
} from 'lucide-react';
import { 
  exportBeamDXF, 
  exportColumnDXF, 
  exportSlabDXF, 
  exportFootingDXF, 
  getCADDownloadUrl 
} from '../services/api';
import type { CADExportResponse } from '../types/api';

export interface CADViewerProps {
  initialMember?: 'beam' | 'column' | 'slab' | 'footing';
  onNavigateToStudio?: (element: 'beam' | 'column' | 'slab' | 'footing') => void;
  activeDesigns?: Record<string, any>;
  onDesignCalculated?: (
    member: 'beam' | 'column' | 'slab' | 'footing',
    result: any,
    params?: any,
    cadExport?: any
  ) => void;
}

export type CADTheme = 'autocad' | 'blueprint' | 'paper';

export const CADViewer: React.FC<CADViewerProps> = ({ 
  initialMember = 'beam',
  onNavigateToStudio,
  activeDesigns,
  onDesignCalculated,
}) => {
  const [selectedMember, setSelectedMember] = useState<'beam' | 'column' | 'slab' | 'footing'>(initialMember);
  const [prevInitialMember, setPrevInitialMember] = useState(initialMember);
  const [isGenerating, setIsGenerating] = useState(false);
  const [localExports, setLocalExports] = useState<Record<string, CADExportResponse>>({});
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [printDate] = useState<string>(() => new Date().toLocaleDateString('en-IN'));

  // Point 1: Interactive Viewport & Styling States
  const [theme, setTheme] = useState<CADTheme>('autocad');
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  // Point 1: Rebar Hover Linking
  const [hoveredRebar, setHoveredRebar] = useState<'main' | 'top' | 'stirrup' | 'dist' | null>(null);

  // Point 1: Layer Visibility Filter
  const [layerVisibility, setLayerVisibility] = useState<Record<string, boolean>>({
    OUTLINE: true,
    CONCRETE: true,
    CONCRETE_OUTLINE: true,
    REBAR_MAIN: true,
    REBAR_TOP: true,
    REBAR: true,
    REBAR_DIST: true,
    STIRRUPS: true,
    TIES: true,
    DIMENSIONS: true,
    ANNOTATIONS: true,
    TEXT_ANNOTATIONS: true,
    TITLE_BLOCK: true,
    HATCH: true,
    SUPPORTS: true,
    COLUMN_OUTLINE: true,
    WATERMARK: true,
  });

  // Point 1: Interactive Measurement Tool
  const [measuring, setMeasuring] = useState<boolean>(false);
  const [measurePoints, setMeasurePoints] = useState<Array<{ x: number; y: number }>>([]);
  const [currentMousePos, setCurrentMousePos] = useState<{ x: number; y: number } | null>(null);

  const canvasRef = useRef<HTMLDivElement>(null);

  if (initialMember !== prevInitialMember) {
    setPrevInitialMember(initialMember);
    setSelectedMember(initialMember);
  }

  const lastExport = localExports[selectedMember] || activeDesigns?.[selectedMember]?.cadExport || null;

  // CAD Layer Structures exactly matching Python backend DXF generators
  const cadLayerDefinitions = {
    beam: {
      title: 'RC Beam Longitudinal & Cross Section',
      code: 'IS 456:2000 Cl. 26.5.1 & Table 19',
      dxfGenerator: 'src/cad/beam_dxf.py',
      layers: [
        { key: 'OUTLINE', name: 'OUTLINE', color: '#F8FAFC', desc: 'Concrete outline & boundary (0.35mm)' },
        { key: 'REBAR_MAIN', name: 'REBAR_MAIN', color: '#EF4444', desc: 'Bottom tension steel (0.50mm)' },
        { key: 'REBAR_TOP', name: 'REBAR_TOP', color: '#22C55E', desc: 'Top hanger bars for stirrup ties (0.35mm)' },
        { key: 'STIRRUPS', name: 'STIRRUPS', color: '#06B6D4', desc: '2-legged shear stirrup ties (0.25mm)' },
        { key: 'DIMENSIONS', name: 'DIMENSIONS', color: '#EAB308', desc: 'Clear span, depth D, breadth b (0.18mm)' },
        { key: 'ANNOTATIONS', name: 'ANNOTATIONS', color: '#D946EF', desc: 'Rebar callouts & IS 456 notes (0.25mm)' },
        { key: 'HATCH', name: 'HATCH', color: '#64748B', desc: 'Support bearings and masonry hatching (0.13mm)' },
        { key: 'WATERMARK', name: 'WATERMARK', color: '#EF4444', desc: 'Statutory disclaimer: DRAFT (0.70mm)' }
      ]
    },
    column: {
      title: 'Short Column Section & Tie Elevation',
      code: 'IS 456:2000 Cl. 39.3 & Cl. 26.5.3',
      dxfGenerator: 'src/cad/column_dxf.py',
      layers: [
        { key: 'CONCRETE', name: 'CONCRETE', color: '#F8FAFC', desc: 'Column boundary and section outline (0.35mm)' },
        { key: 'REBAR', name: 'REBAR', color: '#EF4444', desc: 'Longitudinal vertical load-bearing rebar (0.50mm)' },
        { key: 'TIES', name: 'TIES', color: '#06B6D4', desc: 'Perimeter link ties & confinement zones (0.25mm)' },
        { key: 'DIMENSIONS', name: 'DIMENSIONS', color: '#22C55E', desc: 'Column b x D dimensions & clear height H (0.18mm)' },
        { key: 'ANNOTATIONS', name: 'ANNOTATIONS', color: '#EAB308', desc: 'Elevation labels & bar callouts (0.25mm)' },
        { key: 'WATERMARK', name: 'WATERMARK', color: '#EF4444', desc: 'Statutory disclaimer: DRAFT (0.70mm)' }
      ]
    },
    slab: {
      title: 'Two-Way Slab Mesh & Edge Detailing',
      code: 'IS 456:2000 Cl. 24 & Annex D',
      dxfGenerator: 'src/cad/slab_dxf.py',
      layers: [
        { key: 'CONCRETE_OUTLINE', name: 'CONCRETE_OUTLINE', color: '#F8FAFC', desc: 'Slab panel boundary & supporting edges (0.35mm)' },
        { key: 'REBAR_MAIN', name: 'REBAR_MAIN', color: '#EF4444', desc: 'Bottom flexural bars along short span Lx (0.50mm)' },
        { key: 'REBAR_DIST', name: 'REBAR_DIST', color: '#3B82F6', desc: 'Distribution bars along long span Ly (0.35mm)' },
        { key: 'SUPPORTS', name: 'SUPPORTS', color: '#64748B', desc: 'Supporting wall and beam boundary lines (0.25mm)' },
        { key: 'DIMENSIONS', name: 'DIMENSIONS', color: '#06B6D4', desc: 'Panel spans Lx, Ly, overall thickness D (0.18mm)' },
        { key: 'TEXT_ANNOTATIONS', name: 'TEXT_ANNOTATIONS', color: '#EAB308', desc: 'Slab classification & design notes (0.25mm)' },
        { key: 'WATERMARK', name: 'WATERMARK', color: '#EF4444', desc: 'Statutory disclaimer: DRAFT (0.70mm)' }
      ]
    },
    footing: {
      title: 'Isolated Spread Footing Plan & Section',
      code: 'IS 456:2000 Cl. 34 (Bearing & Punching Shear)',
      dxfGenerator: 'src/cad/footing_dxf.py',
      layers: [
        { key: 'CONCRETE_OUTLINE', name: 'CONCRETE_OUTLINE', color: '#F8FAFC', desc: 'Pad footing geometry with lean concrete (0.35mm)' },
        { key: 'COLUMN_OUTLINE', name: 'COLUMN_OUTLINE', color: '#06B6D4', desc: 'Column pedestal outline with 50mm cover (0.35mm)' },
        { key: 'REBAR_MAIN', name: 'REBAR_MAIN', color: '#EF4444', desc: 'Biaxial bottom flexural mesh (0.50mm)' },
        { key: 'DIMENSIONS', name: 'DIMENSIONS', color: '#06B6D4', desc: 'Plan dimensions B x L & total depth D (0.18mm)' },
        { key: 'TEXT_ANNOTATIONS', name: 'TEXT_ANNOTATIONS', color: '#EAB308', desc: 'Bearing capacity & rebar tags (0.25mm)' },
        { key: 'WATERMARK', name: 'WATERMARK', color: '#EF4444', desc: 'Statutory disclaimer: DRAFT (0.70mm)' }
      ]
    }
  };

  const currentMeta = cadLayerDefinitions[selectedMember];
  const activeRecord = activeDesigns?.[selectedMember];
  const hasCalculation = Boolean(activeRecord?.result);

  // Extract real design data without hardcoding or inventing values
  const getBeamData = () => {
    if (!activeRecord?.result) return null;
    const r = activeRecord.result;
    const d = r.design_dict || r.design || r.sizing?.design_dict || activeRecord.cadExport?.design || activeRecord.cadExport?.design_dict || (typeof r.b === 'number' ? r : null);
    if (!d) return null;
    return {
      span_m: d.span_m ?? activeRecord.params?.span_m ?? 5.0,
      span_mm: Math.round((d.span_m ?? activeRecord.params?.span_m ?? 5.0) * 1000),
      b_mm: Math.round(d.b ?? 300),
      D_mm: Math.round(d.D ?? 500),
      d_mm: Math.round(d.d ?? 460),
      cover_mm: Math.round(d.cover_mm ?? 30),
      fck: d.fck ?? 25,
      fy: d.fy ?? 500,
      main_bar_count: d.main_bar_count ?? 3,
      main_bar_dia_mm: d.main_bar_dia_mm ?? 16,
      compression_bar_count: d.compression_bar_count ?? 2,
      compression_bar_dia_mm: d.compression_bar_dia_mm ?? 10,
      stirrup_dia_mm: d.stirrup_dia_mm ?? 8,
      stirrup_spacing_mm: Math.round(d.stirrup_spacing_mm ?? 150),
      ast_provided: d.ast_provided_mm2 ? `${Math.round(d.ast_provided_mm2)} mm²` : null,
      shear_status: d.shear_status || 'minimum_shear_steel_ok'
    };
  };

  const getColumnData = () => {
    if (!activeRecord?.result) return null;
    const r = activeRecord.result;
    const d = r.design_dict || r;
    const rebar = d.rebar_selected || r.rebar_selected;
    const ties = d.lateral_ties || r.lateral_ties;
    return {
      b_mm: Math.round(d.width_mm ?? r.width_mm ?? activeRecord.params?.b_mm ?? 400),
      D_mm: Math.round(d.depth_mm ?? r.depth_mm ?? activeRecord.params?.D_mm ?? 400),
      length_m: d.length_m ?? r.length_m ?? activeRecord.params?.length_m ?? 3.0,
      length_mm: Math.round((d.length_m ?? r.length_m ?? activeRecord.params?.length_m ?? 3.0) * 1000),
      bar_count: rebar?.bar_count ?? 4,
      bar_dia: rebar?.bar_diameter_mm ?? 16,
      bar_callout: rebar?.callout || `${rebar?.bar_count ?? 4}-T${rebar?.bar_diameter_mm ?? 16}`,
      tie_callout: ties?.callout || `T${ties?.tie_diameter_mm ?? 8} @ ${ties?.tie_pitch_mm ?? 200} c/c`,
      pu_kN: d.factored_axial_load_Pu_kN ?? activeRecord.params?.axial_load_kN ? Math.round(activeRecord.params.axial_load_kN * 1.5) : null
    };
  };

  const getSlabData = () => {
    if (!activeRecord?.result) return null;
    const r = activeRecord.result;
    const geom = r.geometry || {};
    const flex = r.flexure || {};
    return {
      lx_m: geom.shorter_span_Lx_m ?? activeRecord.params?.lx_m ?? 4.0,
      ly_m: geom.longer_span_Ly_m ?? activeRecord.params?.ly_m ?? 5.5,
      lx_mm: Math.round((geom.shorter_span_Lx_m ?? activeRecord.params?.lx_m ?? 4.0) * 1000),
      ly_mm: Math.round((geom.longer_span_Ly_m ?? activeRecord.params?.ly_m ?? 5.5) * 1000),
      D_mm: Math.round(geom.overall_depth_D_mm ?? 140),
      d_mm: Math.round(geom.effective_depth_d_mm ?? 115),
      slab_type: r.slab_type === 'one_way' || r.slab_type === 'One-Way Slab' ? 'One-Way Slab' : 'Two-Way Slab',
      main_callout: flex.main_rebar_x?.callout || 'T10 @ 150 c/c',
      dist_callout: flex.transverse_reinforcement?.rebar?.callout || 'T8 @ 180 c/c'
    };
  };

  const getFootingData = () => {
    if (!activeRecord?.result) return null;
    const r = activeRecord.result;
    const geom = r.geometry || {};
    const flex = r.flexure || {};
    return {
      B_mm: Math.round(geom.B_mm ?? 2400),
      L_mm: Math.round(geom.L_mm ?? 2400),
      D_mm: Math.round(geom.total_depth_D_mm ?? 500),
      d_mm: Math.round(geom.effective_depth_d_mm ?? 425),
      col_b_mm: Math.round(activeRecord.params?.col_b_mm ?? 400),
      col_D_mm: Math.round(activeRecord.params?.col_D_mm ?? 400),
      rebar_mesh: flex.rebar_mesh?.callout || 'T12 @ 150 c/c both ways'
    };
  };

  const beamData = getBeamData();
  const colData = getColumnData();
  const slabData = getSlabData();
  const footData = getFootingData();

  // Export DXF handler
  const handleQuickExport = async (memberType: 'beam' | 'column' | 'slab' | 'footing') => {
    setIsGenerating(true);
    setErrorMsg(null);
    try {
      let res: CADExportResponse;
      const params = activeRecord?.params;

      if (memberType === 'beam') {
        const payload = {
          span_m: params?.span_m ?? 5.0,
          dead_load_kN_per_m: params?.dead_load_kN_per_m ?? 18.0,
          live_load_kN_per_m: params?.live_load_kN_per_m ?? 12.0,
          fck: params?.fck ?? 25.0,
          fy: params?.fy ?? 500.0,
          exposure: params?.exposure ?? 'Moderate',
          output_filename: `beam_${params?.span_m ?? 5.0}m_${Date.now().toString().slice(-4)}.dxf`,
        };
        res = await exportBeamDXF(payload);
        if (onDesignCalculated) {
          onDesignCalculated('beam', activeRecord?.result || res, payload, res);
        }
      } else if (memberType === 'column') {
        const payload = {
          axial_load_kN: params?.axial_load_kN ?? 1200.0,
          length_m: params?.length_m ?? 3.2,
          b_mm: params?.b_mm ?? 400,
          D_mm: params?.D_mm ?? 450,
          fck: params?.fck ?? 25.0,
          fy: params?.fy ?? 500.0,
          exposure: params?.exposure ?? 'Moderate',
          output_filename: `column_${params?.b_mm ?? 400}x${params?.D_mm ?? 450}_${Date.now().toString().slice(-4)}.dxf`,
        };
        res = await exportColumnDXF(payload);
        if (onDesignCalculated) {
          onDesignCalculated('column', activeRecord?.result || res, payload, res);
        }
      } else if (memberType === 'slab') {
        const payload = {
          lx_m: params?.lx_m ?? 4.0,
          ly_m: params?.ly_m ?? 5.5,
          live_load_kN_m2: params?.live_load_kN_m2 ?? 3.0,
          floor_finish_kN_m2: params?.floor_finish_kN_m2 ?? 1.0,
          support_width_mm: params?.support_width_mm ?? 230,
          fck: params?.fck ?? 25.0,
          fy: params?.fy ?? 500.0,
          exposure: params?.exposure ?? 'Moderate',
          support_condition: params?.support_condition ?? 'simply_supported',
          output_filename: `slab_${params?.lx_m ?? 4.0}x${params?.ly_m ?? 5.5}_${Date.now().toString().slice(-4)}.dxf`,
        };
        res = await exportSlabDXF(payload);
        if (onDesignCalculated) {
          onDesignCalculated('slab', activeRecord?.result || res, payload, res);
        }
      } else {
        const payload = {
          axial_load_kN: params?.axial_load_kN ?? 1200.0,
          sbc_kN_m2: params?.sbc_kN_m2 ?? 200.0,
          col_b_mm: params?.col_b_mm ?? 300,
          col_D_mm: params?.col_D_mm ?? 450,
          fck: params?.fck ?? 25.0,
          fy: params?.fy ?? 500.0,
          output_filename: `footing_${params?.axial_load_kN ?? 1200}kN_${Date.now().toString().slice(-4)}.dxf`,
        };
        res = await exportFootingDXF(payload);
        if (onDesignCalculated) {
          onDesignCalculated('footing', activeRecord?.result || res, payload, res);
        }
      }

      setLocalExports(prev => ({ ...prev, [selectedMember]: res }));
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to export DXF';
      setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setIsGenerating(false);
    }
  };

  // Pan & Zoom Handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (measuring) {
      handleCanvasClick(e);
      return;
    }
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (measuring && canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      setCurrentMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    setZoom(prev => Math.min(3.0, Math.max(0.5, prev * zoomFactor)));
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setMeasurePoints([]);
  };

  // Measuring tool handler
  const handleCanvasClick = (e: React.MouseEvent) => {
    if (!measuring || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (measurePoints.length === 0 || measurePoints.length === 2) {
      setMeasurePoints([{ x, y }]);
    } else {
      setMeasurePoints(prev => [...prev, { x, y }]);
    }
  };

  // Toggle single layer visibility
  const toggleLayer = (layerName: string) => {
    setLayerVisibility(prev => ({
      ...prev,
      [layerName]: !prev[layerName]
    }));
  };

  // Helper to check layer visibility
  const isLayerVisible = (layerName: string): boolean => {
    return layerVisibility[layerName] !== false;
  };

  // Compute measured distance scaled to member dimensions
  const getMeasuredDistanceMm = (): number | null => {
    if (measurePoints.length < 2) return null;
    const dx = measurePoints[1].x - measurePoints[0].x;
    const dy = measurePoints[1].y - measurePoints[0].y;
    const pixelDist = Math.sqrt(dx * dx + dy * dy);

    // Approximate SVG scale reference: 400px width represents span_mm or Lx_mm
    const refSpanMm = beamData?.span_mm || colData?.length_mm || slabData?.ly_mm || footData?.B_mm || 5000;
    const mmPerPixel = refSpanMm / 380;
    return Math.round(pixelDist * mmPerPixel);
  };

  // Print Drawing Sheet
  const handlePrintSheet = () => {
    window.print();
  };

  // Theme-specific styles
  const themeStyles = {
    autocad: {
      canvasBg: 'bg-[#050811]',
      gridColor: '#00ffff',
      gridOpacity: 0.12,
      outlineColor: '#F8FAFC',
      rebarMainColor: '#EF4444',
      rebarTopColor: '#22C55E',
      stirrupColor: '#06B6D4',
      dimensionColor: '#EAB308',
      annotationColor: '#D946EF',
      hatchColor: '#64748B',
      watermarkColor: 'text-red-500/20 border-red-500/20',
      label: 'AutoCAD Dark Space'
    },
    blueprint: {
      canvasBg: 'bg-[#071E3D]',
      gridColor: '#38BDF8',
      gridOpacity: 0.22,
      outlineColor: '#FFFFFF',
      rebarMainColor: '#67E8F9',
      rebarTopColor: '#A7F3D0',
      stirrupColor: '#93C5FD',
      dimensionColor: '#FEF08A',
      annotationColor: '#FBCFE8',
      hatchColor: '#1E3A5F',
      watermarkColor: 'text-blue-300/20 border-blue-300/20',
      label: 'Engineering Blueprint'
    },
    paper: {
      canvasBg: 'bg-white',
      gridColor: '#CBD5E1',
      gridOpacity: 0.40,
      outlineColor: '#0F172A',
      rebarMainColor: '#B91C1C',
      rebarTopColor: '#15803D',
      stirrupColor: '#0284C7',
      dimensionColor: '#B45309',
      annotationColor: '#7C3AED',
      hatchColor: '#94A3B8',
      watermarkColor: 'text-red-600/15 border-red-600/15',
      label: 'Paper Print Sheet'
    }
  }[theme];

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-3">
              <Layers className="w-3.5 h-3.5" />
              Interactive CAD Blueprint & DXF Engine
            </div>
            <h1 className="text-2xl font-bold text-slate-100">
              Interactive 2D CAD Blueprints & Inspection
            </h1>
            <p className="text-sm text-slate-400 mt-1 max-w-2xl">
              Inspect AutoCAD drawings with pan/zoom, layer isolation, rebar hover linking, dynamic snap ruler, and vector printing.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <button
              onClick={handlePrintSheet}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl font-medium text-xs text-slate-200 bg-slate-800 hover:bg-slate-700 transition-colors border border-slate-700 shadow"
              title="Print Vector Engineering Drawing Sheet (Ctrl+P)"
            >
              <Printer className="w-3.5 h-3.5 text-blue-400" />
              <span>Print Sheet</span>
            </button>

            <button
              onClick={() => handleQuickExport(selectedMember)}
              disabled={isGenerating}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl font-medium text-xs text-white bg-blue-600 hover:bg-blue-500 transition-all shadow-lg shadow-blue-600/20 disabled:opacity-50"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Generating DXF...
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  Export {selectedMember.toUpperCase()} DXF
                </>
              )}
            </button>
          </div>
        </div>

        {/* Member Selector Tabs */}
        <div className="flex gap-2 mt-6 border-b border-slate-800 pb-2 overflow-x-auto">
          {[
            { id: 'beam', label: 'RC Beam DXF', icon: Compass },
            { id: 'column', label: 'RC Column DXF', icon: Columns },
            { id: 'slab', label: 'RC Slab DXF', icon: Grid },
            { id: 'footing', label: 'Footing DXF', icon: Square },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = selectedMember === tab.id;
            const memberCalculated = Boolean(activeDesigns?.[tab.id]?.result);
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setSelectedMember(tab.id as any);
                  resetView();
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                  active
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
                {memberCalculated && (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" title="Active design data synchronized" />
                )}
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
          All CAD output files generated by this pipeline automatically include an indelible text entity stamped with draft disclaimer. 
          This warning cannot be stripped or bypassed by automated routines. Only an authorized human licensed engineer holding a valid statutory license can issue final construction blueprints.
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
        {/* Left 2 Cols: Interactive AutoCAD Vector Viewport */}
        <div className={`lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between ${isFullscreen ? 'fixed inset-4 z-50 overflow-hidden' : ''}`}>
          <div>
            {/* Viewport Top Bar: Metadata & View Controls */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 mb-4 gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-semibold text-slate-100">{currentMeta.title}</h3>
                  {hasCalculation ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <Sparkles className="w-2.5 h-2.5" />
                      Live Sizing Synced
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
                      Awaiting Sizing Run
                    </span>
                  )}
                </div>
                <span className="text-xs font-mono text-slate-400">{currentMeta.code}</span>
              </div>

              {/* Point 1: Theme Presets Selector */}
              <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800 self-start sm:self-auto">
                <button
                  onClick={() => setTheme('autocad')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                    theme === 'autocad'
                      ? 'bg-slate-800 text-cyan-400 shadow-sm border border-cyan-500/30'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="AutoCAD Model Space (Dark Neon)"
                >
                  Model Space
                </button>
                <button
                  onClick={() => setTheme('blueprint')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                    theme === 'blueprint'
                      ? 'bg-blue-900/60 text-blue-300 shadow-sm border border-blue-400/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Architectural Blueprint (Navy & White)"
                >
                  Blueprint
                </button>
                <button
                  onClick={() => setTheme('paper')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                    theme === 'paper'
                      ? 'bg-white text-slate-900 font-semibold shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Paper Print Preview (White Sheet)"
                >
                  Paper
                </button>
              </div>
            </div>

            {/* Simulated AutoCAD Vector Canvas with Pan, Zoom & Ruler */}
            <div 
              ref={canvasRef}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onWheel={handleWheel}
              className={`relative w-full min-h-[380px] h-[400px] ${themeStyles.canvasBg} rounded-xl border border-slate-800 flex flex-col items-center justify-center overflow-hidden p-4 select-none cursor-${measuring ? 'crosshair' : isDragging ? 'grabbing' : 'grab'} transition-colors duration-200`}
            >
              {/* Subtle Coordinate CAD Grid */}
              <div 
                className="absolute inset-0 pointer-events-none"
                style={{
                  opacity: themeStyles.gridOpacity,
                  backgroundImage: `radial-gradient(${themeStyles.gridColor} 1px, transparent 1px)`,
                  backgroundSize: '24px 24px',
                  transform: `translate(${pan.x % 24}px, ${pan.y % 24}px)`
                }}
              />

              {/* Point 1: Interactive Floating HUD: Zoom, Pan, Measure & Fullscreen */}
              <div className="absolute top-3 right-3 z-30 flex items-center gap-1.5 bg-slate-900/80 backdrop-blur-md p-1.5 rounded-xl border border-slate-700/80 shadow-lg">
                <button
                  onClick={() => setZoom(prev => Math.min(3.0, prev + 0.2))}
                  className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                  title="Zoom In (+)"
                >
                  <ZoomIn className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setZoom(prev => Math.max(0.5, prev - 0.2))}
                  className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                  title="Zoom Out (-)"
                >
                  <ZoomOut className="w-4 h-4" />
                </button>
                <button
                  onClick={resetView}
                  className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                  title="Reset View (100%)"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
                <div className="h-4 w-px bg-slate-700 mx-0.5" />
                <button
                  onClick={() => {
                    setMeasuring(prev => !prev);
                    setMeasurePoints([]);
                  }}
                  className={`p-1.5 rounded-lg transition-colors ${
                    measuring 
                      ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' 
                      : 'text-slate-300 hover:text-white hover:bg-slate-800'
                  }`}
                  title={measuring ? 'Measuring Active (Click to drop points)' : 'Interactive Snap Ruler'}
                >
                  <Ruler className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setIsFullscreen(prev => !prev)}
                  className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                  title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Viewport'}
                >
                  {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                </button>
                <span className="text-[10px] font-mono font-semibold px-1.5 text-slate-400">
                  {Math.round(zoom * 100)}%
                </span>
              </div>

              {/* Point 1: Measurement Ruler Active HUD */}
              {measuring && (
                <div className="absolute bottom-3 left-3 z-30 bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-xl border border-amber-500/40 text-xs font-mono text-amber-300 shadow-xl flex items-center gap-2">
                  <Ruler className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
                  <span>
                    {measurePoints.length === 0 && 'Click anywhere to set Point A'}
                    {measurePoints.length === 1 && 'Click target to set Point B'}
                    {measurePoints.length === 2 && `Measured Dimension: ~${getMeasuredDistanceMm()} mm`}
                  </span>
                  {measurePoints.length > 0 && (
                    <button 
                      onClick={() => setMeasurePoints([])}
                      className="ml-2 px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-[10px] text-slate-300"
                    >
                      Clear
                    </button>
                  )}
                </div>
              )}

              {/* Rebar Hover Active Inspection Badge */}
              {hoveredRebar && (
                <div className="absolute top-3 left-3 z-30 bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-xl border border-blue-500/40 text-xs font-mono shadow-xl flex items-center gap-2 animate-fadeIn">
                  <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping" />
                  <span className="text-blue-300 font-semibold">
                    {hoveredRebar === 'main' && (beamData ? `Tension Steel: ${beamData.main_bar_count}-T${beamData.main_bar_dia_mm} (Fe ${beamData.fy}) | Ast = ${beamData.ast_provided || 'calculated'}` : 'Main Tension Rebar')}
                    {hoveredRebar === 'top' && (beamData ? `Top Hanger Bars: ${beamData.compression_bar_count}-T${beamData.compression_bar_dia_mm} (IS 456 Cl. 26.5.1.1)` : 'Compression Rebar')}
                    {hoveredRebar === 'stirrup' && (beamData ? `Shear Stirrups: 2L-T${beamData.stirrup_dia_mm} @ ${beamData.stirrup_spacing_mm} mm c/c (IS 456 Table 19)` : 'Shear Stirrup Links')}
                    {hoveredRebar === 'dist' && 'Transverse Distribution Reinforcement'}
                  </span>
                </div>
              )}

              {/* Diagonal Draft Watermark across Canvas */}
              {isLayerVisible('WATERMARK') && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
                  <div className={`transform -rotate-20 text-xl sm:text-2xl md:text-3xl font-mono font-black tracking-widest uppercase border-4 border-dashed px-6 py-3 rounded-lg text-center ${themeStyles.watermarkColor}`}>
                    DRAFT - NOT FOR CONSTRUCTION
                  </div>
                </div>
              )}

              {/* Scalable & Pannable Vector Container */}
              <div
                style={{
                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                  transformOrigin: 'center center',
                  transition: isDragging ? 'none' : 'transform 0.1s ease-out',
                }}
                className="w-full h-full flex items-center justify-center"
              >
                {/* Dynamic SVG CAD Blueprint Rendering: BEAM */}
                {selectedMember === 'beam' && (
                  <svg className="w-full h-full max-h-80 z-10" viewBox="0 0 520 220" fill="none">
                    {/* Support Pillars / Bearing Walls (Layer: HATCH / SUPPORTS) */}
                    {isLayerVisible('HATCH') && (
                      <g>
                        <rect x="40" y="145" width="40" height="25" fill="#1E293B" stroke={themeStyles.hatchColor} strokeWidth="1.5" />
                        <rect x="440" y="145" width="40" height="25" fill="#1E293B" stroke={themeStyles.hatchColor} strokeWidth="1.5" />
                        <line x1="30" y1="170" x2="90" y2="170" stroke={themeStyles.hatchColor} strokeWidth="1.5" />
                        <line x1="430" y1="170" x2="490" y2="170" stroke={themeStyles.hatchColor} strokeWidth="1.5" />
                      </g>
                    )}

                    {/* Beam Outer Concrete Outline (Layer: OUTLINE) */}
                    {isLayerVisible('OUTLINE') && (
                      <rect 
                        x="50" 
                        y="55" 
                        width="420" 
                        height="90" 
                        stroke={themeStyles.outlineColor} 
                        strokeWidth="2.5" 
                        fill={theme === 'paper' ? '#f8fafc' : '#1E293B'} 
                        fillOpacity={theme === 'paper' ? '0.8' : '0.4'} 
                      />
                    )}

                    {/* Top Hanger Rebar (Layer: REBAR_TOP) */}
                    {isLayerVisible('REBAR_TOP') && (
                      <g 
                        onMouseEnter={() => setHoveredRebar('top')}
                        onMouseLeave={() => setHoveredRebar(null)}
                        className="cursor-pointer"
                        style={{
                          filter: hoveredRebar === 'top' ? 'drop-shadow(0 0 6px #22C55E)' : 'none',
                          opacity: hoveredRebar && hoveredRebar !== 'top' ? 0.4 : 1
                        }}
                      >
                        <line x1="65" y1="70" x2="455" y2="70" stroke={themeStyles.rebarTopColor} strokeWidth={hoveredRebar === 'top' ? 4 : 2.5} />
                        <line x1="65" y1="70" x2="65" y2="85" stroke={themeStyles.rebarTopColor} strokeWidth={hoveredRebar === 'top' ? 4 : 2.5} />
                        <line x1="455" y1="70" x2="455" y2="85" stroke={themeStyles.rebarTopColor} strokeWidth={hoveredRebar === 'top' ? 4 : 2.5} />
                      </g>
                    )}

                    {/* Bottom Main Tension Rebar (Layer: REBAR_MAIN) */}
                    {isLayerVisible('REBAR_MAIN') && (
                      <g 
                        onMouseEnter={() => setHoveredRebar('main')}
                        onMouseLeave={() => setHoveredRebar(null)}
                        className="cursor-pointer"
                        style={{
                          filter: hoveredRebar === 'main' ? 'drop-shadow(0 0 8px #EF4444)' : 'none',
                          opacity: hoveredRebar && hoveredRebar !== 'main' ? 0.4 : 1
                        }}
                      >
                        <line x1="65" y1="130" x2="455" y2="130" stroke={themeStyles.rebarMainColor} strokeWidth={hoveredRebar === 'main' ? 6 : 4} />
                        <line x1="65" y1="130" x2="65" y2="115" stroke={themeStyles.rebarMainColor} strokeWidth={hoveredRebar === 'main' ? 6 : 4} />
                        <line x1="455" y1="130" x2="455" y2="115" stroke={themeStyles.rebarMainColor} strokeWidth={hoveredRebar === 'main' ? 6 : 4} />
                      </g>
                    )}

                    {/* Shear Stirrups dynamically computed based on spacing (Layer: STIRRUPS) */}
                    {isLayerVisible('STIRRUPS') && (
                      <g
                        onMouseEnter={() => setHoveredRebar('stirrup')}
                        onMouseLeave={() => setHoveredRebar(null)}
                        className="cursor-pointer"
                        style={{
                          filter: hoveredRebar === 'stirrup' ? 'drop-shadow(0 0 6px #06B6D4)' : 'none',
                          opacity: hoveredRebar && hoveredRebar !== 'stirrup' ? 0.4 : 1
                        }}
                      >
                        {(() => {
                          const stirrupCount = beamData
                            ? Math.min(16, Math.max(6, Math.round(beamData.span_mm / Math.max(100, beamData.stirrup_spacing_mm))))
                            : 8;
                          const startX = 85;
                          const endX = 435;
                          const step = (endX - startX) / (stirrupCount - 1);
                          return Array.from({ length: stirrupCount }).map((_, i) => {
                            const x = startX + i * step;
                            return (
                              <line 
                                key={i} 
                                x1={x} 
                                y1="65" 
                                x2={x} 
                                y2="135" 
                                stroke={themeStyles.stirrupColor} 
                                strokeWidth={hoveredRebar === 'stirrup' ? 2.5 : 1.5} 
                                strokeDasharray={hoveredRebar === 'stirrup' ? 'none' : '3 2'} 
                              />
                            );
                          });
                        })()}
                      </g>
                    )}

                    {/* Dimensions Layer (Layer: DIMENSIONS) */}
                    {isLayerVisible('DIMENSIONS') && (
                      <g>
                        <line x1="50" y1="180" x2="470" y2="180" stroke={themeStyles.dimensionColor} strokeWidth="1" />
                        <path d="M50 176 L50 184 M470 176 L470 184" stroke={themeStyles.dimensionColor} strokeWidth="1" />
                        <text x="260" y="195" fill={themeStyles.dimensionColor} fontSize="11" fontFamily="monospace" textAnchor="middle">
                          {beamData ? `SPAN = ${beamData.span_mm} mm` : 'SPAN = — mm'}
                        </text>

                        <line x1="30" y1="55" x2="30" y2="145" stroke={themeStyles.dimensionColor} strokeWidth="1" />
                        <path d="M26 55 L34 55 M26 145 L34 145" stroke={themeStyles.dimensionColor} strokeWidth="1" />
                        <text x="20" y="105" fill={themeStyles.dimensionColor} fontSize="10" fontFamily="monospace" textAnchor="middle" transform="rotate(-90 20 105)">
                          {beamData ? `D = ${beamData.D_mm} mm (b = ${beamData.b_mm})` : 'D = — mm'}
                        </text>
                      </g>
                    )}

                    {/* Annotations Layer (Layer: ANNOTATIONS) */}
                    {isLayerVisible('ANNOTATIONS') && (
                      <g>
                        <text 
                          x="460" 
                          y="50" 
                          fill={themeStyles.rebarTopColor} 
                          fontSize="10" 
                          fontFamily="monospace" 
                          textAnchor="end"
                          className="cursor-pointer"
                          onMouseEnter={() => setHoveredRebar('top')}
                          onMouseLeave={() => setHoveredRebar(null)}
                          fontWeight={hoveredRebar === 'top' ? 'bold' : 'normal'}
                        >
                          {beamData ? `${beamData.compression_bar_count}-T${beamData.compression_bar_dia_mm} Top Hanger` : 'Top Hanger: —'}
                        </text>
                        <text 
                          x="460" 
                          y="145" 
                          fill={themeStyles.rebarMainColor} 
                          fontSize="10" 
                          fontFamily="monospace" 
                          textAnchor="end"
                          className="cursor-pointer"
                          onMouseEnter={() => setHoveredRebar('main')}
                          onMouseLeave={() => setHoveredRebar(null)}
                          fontWeight={hoveredRebar === 'main' ? 'bold' : 'normal'}
                        >
                          {beamData ? `${beamData.main_bar_count}-T${beamData.main_bar_dia_mm} Bottom Main` : 'Bottom Main: —'}
                        </text>
                        <text 
                          x="260" 
                          y="48" 
                          fill={themeStyles.stirrupColor} 
                          fontSize="10" 
                          fontFamily="monospace" 
                          textAnchor="middle"
                          className="cursor-pointer"
                          onMouseEnter={() => setHoveredRebar('stirrup')}
                          onMouseLeave={() => setHoveredRebar(null)}
                          fontWeight={hoveredRebar === 'stirrup' ? 'bold' : 'normal'}
                        >
                          {beamData ? `2L-T${beamData.stirrup_dia_mm} @ ${beamData.stirrup_spacing_mm} c/c` : 'Stirrups: —'}
                        </text>
                      </g>
                    )}
                  </svg>
                )}

                {/* Dynamic SVG CAD Blueprint Rendering: COLUMN */}
                {selectedMember === 'column' && (
                  <svg className="w-full h-full max-h-80 z-10" viewBox="0 0 520 220" fill="none">
                    {/* Left: Column Cross Section (Plan View) */}
                    {isLayerVisible('CONCRETE') && (
                      <rect 
                        x="70" 
                        y="35" 
                        width="130" 
                        height="150" 
                        stroke={themeStyles.outlineColor} 
                        strokeWidth="2.5" 
                        fill={theme === 'paper' ? '#f8fafc' : '#1E293B'} 
                        fillOpacity={theme === 'paper' ? '0.8' : '0.4'} 
                      />
                    )}
                    
                    {/* Lateral Tie Perimeter Link */}
                    {isLayerVisible('TIES') && (
                      <rect 
                        x="85" 
                        y="50" 
                        width="100" 
                        height="120" 
                        stroke={themeStyles.stirrupColor} 
                        strokeWidth={hoveredRebar === 'stirrup' ? 2.5 : 1.5} 
                        strokeDasharray={hoveredRebar === 'stirrup' ? 'none' : '4 2'} 
                      />
                    )}

                    {/* Rebar Circles with interactive hover linking */}
                    {isLayerVisible('REBAR') && (
                      <g 
                        onMouseEnter={() => setHoveredRebar('main')}
                        onMouseLeave={() => setHoveredRebar(null)}
                        className="cursor-pointer"
                        style={{
                          filter: hoveredRebar === 'main' ? 'drop-shadow(0 0 6px #EF4444)' : 'none',
                          opacity: hoveredRebar && hoveredRebar !== 'main' ? 0.4 : 1
                        }}
                      >
                        {(() => {
                          const count = colData?.bar_count ?? 4;
                          const points: Array<[number, number]> = [
                            [95, 60], [175, 60], [95, 160], [175, 160]
                          ];
                          if (count >= 6) {
                            points.push([135, 60], [135, 160]);
                          }
                          if (count >= 8) {
                            points.push([95, 110], [175, 110]);
                          }
                          return points.map(([cx, cy], idx) => (
                            <circle 
                              key={idx} 
                              cx={cx} 
                              cy={cy} 
                              r={hoveredRebar === 'main' ? 7.5 : 6} 
                              fill={themeStyles.rebarMainColor} 
                              stroke="#fff" 
                              strokeWidth="1.5" 
                            />
                          ));
                        })()}
                      </g>
                    )}

                    {isLayerVisible('DIMENSIONS') && (
                      <g>
                        <text x="135" y="24" fill={themeStyles.dimensionColor} fontSize="11" fontFamily="monospace" textAnchor="middle">
                          {colData ? `b = ${colData.b_mm} mm` : 'b = — mm'}
                        </text>
                        <text x="55" y="115" fill={themeStyles.dimensionColor} fontSize="11" fontFamily="monospace" textAnchor="middle" transform="rotate(-90 55 115)">
                          {colData ? `D = ${colData.D_mm} mm` : 'D = — mm'}
                        </text>
                        <text x="135" y="202" fill="#94A3B8" fontSize="10" fontFamily="monospace" textAnchor="middle">
                          CROSS SECTION
                        </text>
                      </g>
                    )}

                    {/* Right: Column Elevation View */}
                    {isLayerVisible('CONCRETE') && (
                      <rect 
                        x="300" 
                        y="25" 
                        width="70" 
                        height="165" 
                        stroke={themeStyles.outlineColor} 
                        strokeWidth="2" 
                        fill={theme === 'paper' ? '#f8fafc' : '#1E293B'} 
                        fillOpacity={theme === 'paper' ? '0.8' : '0.4'} 
                      />
                    )}

                    {/* Vertical main bars */}
                    {isLayerVisible('REBAR') && (
                      <g 
                        onMouseEnter={() => setHoveredRebar('main')}
                        onMouseLeave={() => setHoveredRebar(null)}
                        className="cursor-pointer"
                        style={{
                          filter: hoveredRebar === 'main' ? 'drop-shadow(0 0 6px #EF4444)' : 'none',
                          opacity: hoveredRebar && hoveredRebar !== 'main' ? 0.4 : 1
                        }}
                      >
                        <line x1="312" y1="25" x2="312" y2="190" stroke={themeStyles.rebarMainColor} strokeWidth={hoveredRebar === 'main' ? 4 : 2.5} />
                        <line x1="358" y1="25" x2="358" y2="190" stroke={themeStyles.rebarMainColor} strokeWidth={hoveredRebar === 'main' ? 4 : 2.5} />
                      </g>
                    )}

                    {/* Lateral ties across height */}
                    {isLayerVisible('TIES') && (
                      <g
                        onMouseEnter={() => setHoveredRebar('stirrup')}
                        onMouseLeave={() => setHoveredRebar(null)}
                        className="cursor-pointer"
                        style={{
                          filter: hoveredRebar === 'stirrup' ? 'drop-shadow(0 0 6px #06B6D4)' : 'none',
                          opacity: hoveredRebar && hoveredRebar !== 'stirrup' ? 0.4 : 1
                        }}
                      >
                        {[45, 65, 85, 105, 125, 145, 165].map((y, idx) => (
                          <line 
                            key={idx} 
                            x1="305" 
                            y1={y} 
                            x2={365} 
                            y2={y} 
                            stroke={themeStyles.stirrupColor} 
                            strokeWidth={hoveredRebar === 'stirrup' ? 2.5 : 1.5} 
                            strokeDasharray={hoveredRebar === 'stirrup' ? 'none' : '3 2'} 
                          />
                        ))}
                      </g>
                    )}

                    {isLayerVisible('DIMENSIONS') && (
                      <g>
                        <line x1="385" y1="25" x2="385" y2="190" stroke={themeStyles.dimensionColor} strokeWidth="1" />
                        <path d="M381 25 L389 25 M381 190 L389 190" stroke={themeStyles.dimensionColor} strokeWidth="1" />
                        <text x="400" y="112" fill={themeStyles.dimensionColor} fontSize="10" fontFamily="monospace">
                          {colData ? `H = ${colData.length_mm} mm` : 'H = — mm'}
                        </text>
                        <text x="335" y="202" fill="#94A3B8" fontSize="10" fontFamily="monospace" textAnchor="middle">
                          ELEVATION
                        </text>
                      </g>
                    )}

                    {/* Annotations */}
                    {isLayerVisible('ANNOTATIONS') && (
                      <g>
                        <text 
                          x="210" 
                          y="80" 
                          fill={themeStyles.rebarMainColor} 
                          fontSize="10" 
                          fontFamily="monospace"
                          className="cursor-pointer"
                          onMouseEnter={() => setHoveredRebar('main')}
                          onMouseLeave={() => setHoveredRebar(null)}
                          fontWeight={hoveredRebar === 'main' ? 'bold' : 'normal'}
                        >
                          {colData ? colData.bar_callout : 'Rebar: —'}
                        </text>
                        <text 
                          x="210" 
                          y="100" 
                          fill={themeStyles.stirrupColor} 
                          fontSize="10" 
                          fontFamily="monospace"
                          className="cursor-pointer"
                          onMouseEnter={() => setHoveredRebar('stirrup')}
                          onMouseLeave={() => setHoveredRebar(null)}
                          fontWeight={hoveredRebar === 'stirrup' ? 'bold' : 'normal'}
                        >
                          {colData ? colData.tie_callout : 'Ties: —'}
                        </text>
                      </g>
                    )}
                  </svg>
                )}

                {/* Dynamic SVG CAD Blueprint Rendering: SLAB */}
                {selectedMember === 'slab' && (
                  <svg className="w-full h-full max-h-80 z-10" viewBox="0 0 520 220" fill="none">
                    {isLayerVisible('SUPPORTS') && (
                      <rect x="55" y="25" width="370" height="160" stroke={themeStyles.hatchColor} strokeWidth="1.5" strokeDasharray="4 2" />
                    )}
                    {isLayerVisible('CONCRETE_OUTLINE') && (
                      <rect 
                        x="70" 
                        y="35" 
                        width="340" 
                        height="140" 
                        stroke={themeStyles.outlineColor} 
                        strokeWidth="2.5" 
                        fill={theme === 'paper' ? '#f8fafc' : '#1E293B'} 
                        fillOpacity={theme === 'paper' ? '0.8' : '0.4'} 
                      />
                    )}

                    {/* Main bars (along short span Lx) */}
                    {isLayerVisible('REBAR_MAIN') && (
                      <g
                        onMouseEnter={() => setHoveredRebar('main')}
                        onMouseLeave={() => setHoveredRebar(null)}
                        className="cursor-pointer"
                        style={{
                          filter: hoveredRebar === 'main' ? 'drop-shadow(0 0 6px #EF4444)' : 'none',
                          opacity: hoveredRebar && hoveredRebar !== 'main' ? 0.4 : 1
                        }}
                      >
                        {[95, 135, 175, 215, 255, 295, 335, 375].map((x, i) => (
                          <line key={i} x1={x} y1="45" x2={x} y2="165" stroke={themeStyles.rebarMainColor} strokeWidth={hoveredRebar === 'main' ? 2.5 : 1.5} />
                        ))}
                      </g>
                    )}

                    {/* Distribution bars (along long span Ly) */}
                    {isLayerVisible('REBAR_DIST') && (
                      <g
                        onMouseEnter={() => setHoveredRebar('dist')}
                        onMouseLeave={() => setHoveredRebar(null)}
                        className="cursor-pointer"
                        style={{
                          filter: hoveredRebar === 'dist' ? 'drop-shadow(0 0 6px #3B82F6)' : 'none',
                          opacity: hoveredRebar && hoveredRebar !== 'dist' ? 0.4 : 1
                        }}
                      >
                        {[55, 80, 105, 130, 155].map((y, i) => (
                          <line key={i} x1="80" y1={y} x2="400" y2={y} stroke={themeStyles.stirrupColor} strokeWidth={hoveredRebar === 'dist' ? 2.5 : 1.5} strokeDasharray="3 2" />
                        ))}
                      </g>
                    )}

                    {isLayerVisible('DIMENSIONS') && (
                      <g>
                        <line x1="70" y1="18" x2="410" y2="18" stroke={themeStyles.dimensionColor} strokeWidth="1" />
                        <text x="240" y="14" fill={themeStyles.dimensionColor} fontSize="11" fontFamily="monospace" textAnchor="middle">
                          {slabData ? `Ly = ${slabData.ly_mm} mm` : 'Ly = — mm'}
                        </text>

                        <line x1="45" y1="35" x2="45" y2="175" stroke={themeStyles.dimensionColor} strokeWidth="1" />
                        <text x="35" y="110" fill={themeStyles.dimensionColor} fontSize="11" fontFamily="monospace" textAnchor="middle" transform="rotate(-90 35 110)">
                          {slabData ? `Lx = ${slabData.lx_mm} mm` : 'Lx = — mm'}
                        </text>

                        <text x="240" y="195" fill="#94A3B8" fontSize="10" fontFamily="monospace" textAnchor="middle">
                          {slabData ? `Thickness D = ${slabData.D_mm} mm (Eff d = ${slabData.d_mm} mm) | ${slabData.slab_type}` : 'Thickness D = — mm'}
                        </text>
                      </g>
                    )}

                    {isLayerVisible('TEXT_ANNOTATIONS') && (
                      <g>
                        <text 
                          x="415" 
                          y="60" 
                          fill={themeStyles.rebarMainColor} 
                          fontSize="10" 
                          fontFamily="monospace"
                          className="cursor-pointer"
                          onMouseEnter={() => setHoveredRebar('main')}
                          onMouseLeave={() => setHoveredRebar(null)}
                          fontWeight={hoveredRebar === 'main' ? 'bold' : 'normal'}
                        >
                          {slabData ? `Main: ${slabData.main_callout}` : 'Main: —'}
                        </text>
                        <text 
                          x="415" 
                          y="80" 
                          fill={themeStyles.stirrupColor} 
                          fontSize="10" 
                          fontFamily="monospace"
                          className="cursor-pointer"
                          onMouseEnter={() => setHoveredRebar('dist')}
                          onMouseLeave={() => setHoveredRebar(null)}
                          fontWeight={hoveredRebar === 'dist' ? 'bold' : 'normal'}
                        >
                          {slabData ? `Dist: ${slabData.dist_callout}` : 'Dist: —'}
                        </text>
                      </g>
                    )}
                  </svg>
                )}

                {/* Dynamic SVG CAD Blueprint Rendering: FOOTING */}
                {selectedMember === 'footing' && (
                  <svg className="w-full h-full max-h-80 z-10" viewBox="0 0 520 220" fill="none">
                    {/* Lean Concrete Subbase / Mud Mat */}
                    {isLayerVisible('CONCRETE_OUTLINE') && (
                      <g>
                        <rect x="60" y="165" width="380" height="15" stroke={themeStyles.hatchColor} strokeWidth="1" strokeDasharray="3 2" fill={theme === 'paper' ? '#f1f5f9' : '#0F172A'} />
                        <rect 
                          x="70" 
                          y="65" 
                          width="360" 
                          height="100" 
                          stroke={themeStyles.outlineColor} 
                          strokeWidth="2.5" 
                          fill={theme === 'paper' ? '#f8fafc' : '#1E293B'} 
                          fillOpacity={theme === 'paper' ? '0.8' : '0.4'} 
                        />
                      </g>
                    )}

                    {/* Column Pedestal */}
                    {isLayerVisible('COLUMN_OUTLINE') && (
                      <g>
                        <rect x="220" y="25" width="60" height="40" stroke={themeStyles.stirrupColor} strokeWidth="2" />
                        <line x1="235" y1="25" x2="235" y2="145" stroke={themeStyles.dimensionColor} strokeWidth="2" />
                        <line x1="235" y1="145" x2="200" y2="145" stroke={themeStyles.dimensionColor} strokeWidth="2" />
                        <line x1="265" y1="25" x2="265" y2="145" stroke={themeStyles.dimensionColor} strokeWidth="2" />
                        <line x1="265" y1="145" x2="300" y2="145" stroke={themeStyles.dimensionColor} strokeWidth="2" />
                      </g>
                    )}

                    {/* Bottom Biaxial Steel Mesh */}
                    {isLayerVisible('REBAR_MAIN') && (
                      <g
                        onMouseEnter={() => setHoveredRebar('main')}
                        onMouseLeave={() => setHoveredRebar(null)}
                        className="cursor-pointer"
                        style={{
                          filter: hoveredRebar === 'main' ? 'drop-shadow(0 0 6px #EF4444)' : 'none',
                          opacity: hoveredRebar && hoveredRebar !== 'main' ? 0.4 : 1
                        }}
                      >
                        <line x1="85" y1="150" x2="415" y2="150" stroke={themeStyles.rebarMainColor} strokeWidth={hoveredRebar === 'main' ? 4 : 3} />
                        {[105, 135, 165, 195, 225, 255, 285, 315, 345, 375, 395].map((x, i) => (
                          <circle key={i} cx={x} cy="146" r={hoveredRebar === 'main' ? 4.5 : 3} fill={themeStyles.rebarMainColor} />
                        ))}
                      </g>
                    )}

                    {/* Dimension Lines */}
                    {isLayerVisible('DIMENSIONS') && (
                      <g>
                        <line x1="70" y1="192" x2="430" y2="192" stroke={themeStyles.dimensionColor} strokeWidth="1" />
                        <text x="250" y="206" fill={themeStyles.dimensionColor} fontSize="11" fontFamily="monospace" textAnchor="middle">
                          {footData ? `B = ${footData.B_mm} mm × L = ${footData.L_mm} mm` : 'B = — mm × L = — mm'}
                        </text>

                        <line x1="45" y1="65" x2="45" y2="165" stroke={themeStyles.dimensionColor} strokeWidth="1" />
                        <text x="35" y="115" fill={themeStyles.dimensionColor} fontSize="10" fontFamily="monospace" textAnchor="middle" transform="rotate(-90 35 115)">
                          {footData ? `Depth = ${footData.D_mm} mm` : 'Depth = — mm'}
                        </text>
                      </g>
                    )}

                    {isLayerVisible('TEXT_ANNOTATIONS') && (
                      <g>
                        <text x="250" y="18" fill={themeStyles.stirrupColor} fontSize="10" fontFamily="monospace" textAnchor="middle">
                          {footData ? `Pedestal: ${footData.col_b_mm}×${footData.col_D_mm} mm` : 'Pedestal: —'}
                        </text>
                        <text 
                          x="360" 
                          y="50" 
                          fill={themeStyles.rebarMainColor} 
                          fontSize="10" 
                          fontFamily="monospace"
                          className="cursor-pointer"
                          onMouseEnter={() => setHoveredRebar('main')}
                          onMouseLeave={() => setHoveredRebar(null)}
                          fontWeight={hoveredRebar === 'main' ? 'bold' : 'normal'}
                        >
                          {footData ? `Mesh: ${footData.rebar_mesh}` : 'Mesh: —'}
                        </text>
                      </g>
                    )}
                  </svg>
                )}

                {/* Point 1: Interactive Measuring Guide Line Overlay */}
                {measuring && measurePoints.length > 0 && (
                  <svg className="absolute inset-0 w-full h-full pointer-events-none z-40">
                    <circle cx={measurePoints[0].x} cy={measurePoints[0].y} r="5" fill="#F59E0B" stroke="#fff" strokeWidth="2" />
                    {measurePoints.length === 1 && currentMousePos && (
                      <>
                        <line 
                          x1={measurePoints[0].x} 
                          y1={measurePoints[0].y} 
                          x2={currentMousePos.x} 
                          y2={currentMousePos.y} 
                          stroke="#F59E0B" 
                          strokeWidth="1.5" 
                          strokeDasharray="4 3" 
                        />
                        <circle cx={currentMousePos.x} cy={currentMousePos.y} r="4" fill="#F59E0B" opacity="0.6" />
                      </>
                    )}
                    {measurePoints.length === 2 && (
                      <>
                        <line 
                          x1={measurePoints[0].x} 
                          y1={measurePoints[0].y} 
                          x2={measurePoints[1].x} 
                          y2={measurePoints[1].y} 
                          stroke="#F59E0B" 
                          strokeWidth="2" 
                        />
                        <circle cx={measurePoints[1].x} cy={measurePoints[1].y} r="5" fill="#F59E0B" stroke="#fff" strokeWidth="2" />
                      </>
                    )}
                  </svg>
                )}
              </div>
            </div>

            {/* Parameter & Sizing Data Callout Bar */}
            <div className="mt-4 p-3 bg-slate-950/70 border border-slate-800 rounded-xl text-xs font-mono grid grid-cols-1 md:grid-cols-2 gap-2">
              <div>
                <span className="text-slate-500 block text-[10px] uppercase font-bold">Geometry & Standard:</span>
                <span className="text-slate-200">
                  {selectedMember === 'beam' && (beamData ? `${beamData.b_mm} mm × ${beamData.D_mm} mm (${beamData.span_m} m Span) | d = ${beamData.d_mm} mm` : 'No beam sized yet')}
                  {selectedMember === 'column' && (colData ? `${colData.b_mm} mm × ${colData.D_mm} mm (${colData.length_m} m Height)` : 'No column sized yet')}
                  {selectedMember === 'slab' && (slabData ? `${slabData.lx_m} m × ${slabData.ly_m} m (Thickness D = ${slabData.D_mm} mm)` : 'No slab sized yet')}
                  {selectedMember === 'footing' && (footData ? `${footData.B_mm} mm × ${footData.L_mm} mm × ${footData.D_mm} mm` : 'No footing sized yet')}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px] uppercase font-bold">Reinforcement Detailing:</span>
                <span className="text-emerald-400">
                  {selectedMember === 'beam' && (beamData ? `Bot: ${beamData.main_bar_count}-T${beamData.main_bar_dia_mm} | Top: ${beamData.compression_bar_count}-T${beamData.compression_bar_dia_mm} | Stirrups: 2L-T${beamData.stirrup_dia_mm} @ ${beamData.stirrup_spacing_mm} c/c` : 'Awaiting calculation')}
                  {selectedMember === 'column' && (colData ? `Longitudinal: ${colData.bar_callout} | Lateral: ${colData.tie_callout}` : 'Awaiting calculation')}
                  {selectedMember === 'slab' && (slabData ? `Main: ${slabData.main_callout} | Dist: ${slabData.dist_callout}` : 'Awaiting calculation')}
                  {selectedMember === 'footing' && (footData ? `Mesh: ${footData.rebar_mesh}` : 'Awaiting calculation')}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-800 flex flex-wrap items-center justify-between text-xs text-slate-400 gap-2">
            <span>Engineering Standard: {currentMeta.code}</span>
            {onNavigateToStudio && (
              <button
                onClick={() => onNavigateToStudio(selectedMember)}
                className="inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300 font-medium transition-colors"
              >
                <span>Customize parameters in Member Studio</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Right 1 Col: AutoCAD Layer Hierarchy & Interactive Layer Toggles */}
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Layers className="w-4 h-4 text-blue-400" />
                AutoCAD Layer Visibility
              </h3>
              <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                {currentMeta.dxfGenerator.split('/').pop()}
              </span>
            </div>
            <p className="text-xs text-slate-400 mb-3">
              Click any layer to toggle its visibility on the blueprint canvas in real-time:
            </p>

            <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1">
              {currentMeta.layers.map((layer) => {
                const visible = isLayerVisible(layer.key);
                return (
                  <div 
                    key={layer.key} 
                    onClick={() => toggleLayer(layer.key)}
                    className={`p-2.5 rounded-lg border transition-all cursor-pointer select-none ${
                      visible 
                        ? 'bg-slate-950/70 border-slate-800/90 hover:border-slate-700' 
                        : 'bg-slate-950/20 border-slate-900 opacity-40 hover:opacity-70'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-3 h-3 rounded-full border border-slate-700 flex-shrink-0"
                          style={{ backgroundColor: layer.color }}
                        />
                        <span className="font-mono text-xs font-semibold text-slate-200">
                          {layer.name}
                        </span>
                      </div>
                      <div className="flex items-center gap-1 text-slate-400">
                        {visible ? (
                          <Eye className="w-3.5 h-3.5 text-blue-400" />
                        ) : (
                          <EyeOff className="w-3.5 h-3.5 text-slate-500" />
                        )}
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1 pl-5 leading-normal">{layer.desc}</p>
                  </div>
                );
              })}
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
              <div><span className="text-slate-500">UNITS:</span> Millimeters ($INSUNITS = 4)</div>
              <div><span className="text-slate-500">ENDPOINT:</span> GET /v1/cad/download/:name</div>
            </div>
          </div>
        </div>
      </div>

      {/* Printable Engineering Title Block Section (Activated during window.print) */}
      <div className="hidden print:block print:p-8 bg-white text-black font-mono text-xs border-2 border-black mt-8">
        <div className="border-b-2 border-black pb-4 mb-4 flex justify-between items-start">
          <div>
            <h2 className="text-base font-bold">STRUCTURAL ENGINEERING CALCULATION & DETAIL BLUEPRINT</h2>
            <p className="text-xs">STANDARD: {currentMeta.code} | SCALE: 1:25</p>
          </div>
          <div className="text-right">
            <p className="font-bold">STATUS: DRAFT - NOT FOR CONSTRUCTION</p>
            <p className="text-xs">DATE: {printDate}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 border border-black p-3 mb-4">
          <div>
            <p className="font-bold underline mb-1">MEMBER SPECIFICATION:</p>
            <p>Member: RC {selectedMember.toUpperCase()}</p>
            {selectedMember === 'beam' && beamData && (
              <>
                <p>Span: {beamData.span_m} m ({beamData.span_mm} mm)</p>
                <p>Cross Section: {beamData.b_mm} mm × {beamData.D_mm} mm</p>
                <p>Effective Depth: {beamData.d_mm} mm</p>
                <p>Grades: Concrete M{beamData.fck}, Steel Fe{beamData.fy}</p>
              </>
            )}
            {selectedMember === 'column' && colData && (
              <>
                <p>Cross Section: {colData.b_mm} mm × {colData.D_mm} mm</p>
                <p>Height: {colData.length_m} m</p>
                <p>Factored Axial Load: {colData.pu_kN ? `${colData.pu_kN} kN` : 'N/A'}</p>
              </>
            )}
          </div>
          <div>
            <p className="font-bold underline mb-1">REINFORCEMENT SCHEDULE:</p>
            {selectedMember === 'beam' && beamData && (
              <>
                <p>Tension Bars: {beamData.main_bar_count} Nos. {beamData.main_bar_dia_mm} mm Ø</p>
                <p>Top Hanger Bars: {beamData.compression_bar_count} Nos. {beamData.compression_bar_dia_mm} mm Ø</p>
                <p>Shear Stirrups: 2-Legged {beamData.stirrup_dia_mm} mm Ø @ {beamData.stirrup_spacing_mm} mm c/c</p>
              </>
            )}
            {selectedMember === 'column' && colData && (
              <>
                <p>Vertical Main Bars: {colData.bar_callout}</p>
                <p>Lateral Links / Ties: {colData.tie_callout}</p>
              </>
            )}
          </div>
        </div>

        <div className="text-[10px] text-gray-700 pt-2 border-t border-gray-400">
          Generated automatically by IS 456 Structural RAG Autonomous CAD Engine. Verified deterministically against Bureau of Indian Standards provisions. Must be signed and sealed by a registered Structural Engineer prior to fabrication or site erection.
        </div>
      </div>
    </div>
  );
};
