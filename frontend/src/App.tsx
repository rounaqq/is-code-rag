import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { DashboardOverview } from './components/DashboardOverview';
import { MemberStudio } from './components/MemberStudio';
import { ISCodeSearch } from './components/ISCodeSearch';
import { CADViewer } from './components/CADViewer';
import { ReviewSignoff } from './components/ReviewSignoff';
import { AuditDashboard } from './components/AuditDashboard';
import { AlertTriangle } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [selectedStudioMember, setSelectedStudioMember] = useState<'beam' | 'column' | 'slab' | 'footing'>('beam');

  const handleNavigateFromDashboard = (tab: string) => {
    if (tab === 'beam' || tab === 'column' || tab === 'slab' || tab === 'footing') {
      setSelectedStudioMember(tab);
      setActiveTab('design');
    } else {
      setActiveTab(tab);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleNavigateToStudioFromCAD = (member: 'beam' | 'column' | 'slab' | 'footing') => {
    setSelectedStudioMember(member);
    setActiveTab('design');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navigation */}
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'dashboard' && (
          <DashboardOverview onNavigate={handleNavigateFromDashboard} />
        )}

        {activeTab === 'design' && (
          <MemberStudio initialMember={selectedStudioMember} />
        )}

        {activeTab === 'rag' && (
          <ISCodeSearch />
        )}

        {activeTab === 'cad' && (
          <CADViewer onNavigateToStudio={handleNavigateToStudioFromCAD} />
        )}

        {activeTab === 'review' && (
          <ReviewSignoff />
        )}

        {activeTab === 'observability' && (
          <AuditDashboard />
        )}
      </main>

      {/* Persistent Statutory Safety Footer */}
      <footer className="bg-slate-900 border-t border-slate-800 py-6 mt-12 text-slate-400 text-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 flex-shrink-0">
              <AlertTriangle className="w-4 h-4" />
            </div>
            <div className="space-y-0.5 text-left">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-slate-200">Statutory Watermark:</span>
                <span className="inline-flex px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 whitespace-nowrap">
                  STATUS: DRAFT - NOT FOR CONSTRUCTION
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Deterministic IS 456 calculations and CAD outputs are preliminary computational aids. Execution drawings require registered structural engineer sign-off.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 text-slate-500 font-mono text-[11px] whitespace-nowrap flex-shrink-0">
            <span>IS 456</span>
            <span>•</span>
            <span>IS 13920</span>
            <span>•</span>
            <span>IS 1893</span>
            <span>•</span>
            <span>IS 800</span>
            <span>•</span>
            <span>IS 875</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
