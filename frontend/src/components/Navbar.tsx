import React, { useState, useEffect } from 'react';
import { checkHealth, getStoredApiKey, setStoredApiKey } from '../services/api';
import {
  Compass,
  Key,
  Layers,
  Search,
  FileCheck2,
  BarChart3,
  FileCode,
  Menu,
  X,
  ShieldAlert,
} from 'lucide-react';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [currentKey, setCurrentKey] = useState<string>(getStoredApiKey());
  const [apiKeyInput, setApiKeyInput] = useState(getStoredApiKey());
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const probe = async () => {
      try {
        const res = await checkHealth();
        setIsHealthy(res.status === 'ok');
      } catch {
        setIsHealthy(false);
      }
    };
    probe();
    const interval = setInterval(probe, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const syncKey = () => {
      const k = getStoredApiKey();
      setCurrentKey(k);
      setApiKeyInput(k);
    };
    syncKey();
    const handleOpenModal = () => setShowKeyModal(true);

    window.addEventListener('is_rag_api_key_changed', syncKey);
    window.addEventListener('open_api_key_modal', handleOpenModal);
    return () => {
      window.removeEventListener('is_rag_api_key_changed', syncKey);
      window.removeEventListener('open_api_key_modal', handleOpenModal);
    };
  }, []);

  const handleSaveKey = (e: React.FormEvent) => {
    e.preventDefault();
    setStoredApiKey(apiKeyInput);
    setShowKeyModal(false);
  };

  const navItems = [
    { id: 'dashboard', label: 'Overview', shortLabel: 'Overview', icon: Compass },
    { id: 'design', label: 'Design Studio', shortLabel: 'Design', icon: Layers },
    { id: 'rag', label: 'IS Code Search', shortLabel: 'IS Codes', icon: Search },
    { id: 'cad', label: 'CAD Drawings', shortLabel: 'CAD', icon: FileCode },
    { id: 'review', label: 'Engineer Review', shortLabel: 'Review', icon: FileCheck2 },
    { id: 'observability', label: 'Observability', shortLabel: 'Observability', icon: BarChart3 },
  ];

  const handleTabClick = (id: string) => {
    setActiveTab(id);
    setMobileMenuOpen(false);
  };

  return (
    <>
      <header className="bg-slate-900/95 backdrop-blur-md border-b border-slate-800 text-white sticky top-0 z-50 shadow-lg">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-2">
            {/* Brand Logo & Title */}
            <div
              className="flex items-center gap-2 cursor-pointer select-none flex-shrink-0"
              onClick={() => handleTabClick('dashboard')}
            >
              <div className="bg-gradient-to-tr from-blue-700 to-indigo-500 p-2 rounded-xl text-white shadow-md shadow-blue-500/20 ring-1 ring-white/10 flex-shrink-0">
                <Compass className="h-5 w-5" />
              </div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-base sm:text-lg tracking-tight text-slate-100 whitespace-nowrap">
                  IS Code RAG
                </span>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/30 font-mono tracking-wide whitespace-nowrap">
                  CAD v2.0
                </span>
              </div>
            </div>

            {/* Desktop Navigation Links - Perfectly spaced without scrollbars or clipping */}
            <nav className="hidden lg:flex items-center gap-1 xl:gap-2 flex-shrink-0">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleTabClick(item.id)}
                    className={`flex items-center gap-1.5 px-2.5 xl:px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all duration-150 flex-shrink-0 ${
                      isActive
                        ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30'
                        : 'text-slate-300 hover:text-white hover:bg-slate-800/80'
                    }`}
                  >
                    <Icon className={`h-3.5 w-3.5 flex-shrink-0 ${isActive ? 'text-white' : 'text-blue-400'}`} />
                    <span className="hidden xl:inline">{item.label}</span>
                    <span className="xl:hidden">{item.shortLabel}</span>
                  </button>
                );
              })}
            </nav>

            {/* Right Status Controls */}
            <div className="flex items-center gap-2 flex-shrink-0">
              {/* Backend Heartbeat Pill */}
              <div
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors flex-shrink-0 ${
                  isHealthy === true
                    ? 'bg-emerald-950/60 border-emerald-500/30 text-emerald-300'
                    : isHealthy === false
                    ? 'bg-rose-950/60 border-rose-500/30 text-rose-300'
                    : 'bg-slate-800 border-slate-700 text-slate-400'
                }`}
                title={isHealthy ? 'FastAPI Backend Live on port 8000' : 'FastAPI Backend Disconnected'}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    isHealthy === true ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                  }`}
                />
                <span className="font-mono text-[11px] whitespace-nowrap">
                  {isHealthy === true ? 'API Live' : isHealthy === false ? 'Offline' : 'Connecting'}
                </span>
              </div>

              {/* API Key Modal Button */}
              <button
                onClick={() => {
                  setApiKeyInput(getStoredApiKey());
                  setShowKeyModal(true);
                }}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition flex-shrink-0 ${
                  currentKey
                    ? 'bg-slate-800/80 hover:bg-slate-700 text-slate-200 border-slate-700'
                    : 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border-amber-500/40 animate-pulse'
                }`}
                title="Configure X-API-Key"
              >
                <Key className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
                <span className="text-[11px] whitespace-nowrap">
                  {currentKey ? 'Key Active' : 'Set API Key'}
                </span>
              </button>

              {/* Mobile / Tablet Menu Toggle */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="lg:hidden p-2 rounded-lg bg-slate-800 text-slate-300 hover:text-white border border-slate-700 transition flex-shrink-0"
                aria-label="Toggle Navigation Menu"
              >
                {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile / Narrow Screen Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="lg:hidden border-t border-slate-800 bg-slate-900/98 px-4 py-3 space-y-1 shadow-2xl animate-in fade-in slide-in-from-top-2 duration-150">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleTabClick(item.id)}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
                  }`}
                >
                  <Icon className="h-4 w-4 text-blue-400 flex-shrink-0" />
                  <span className="text-left font-medium">{item.label}</span>
                </button>
              );
            })}

            <div className="pt-2 border-t border-slate-800/80 mt-2">
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  setApiKeyInput(getStoredApiKey());
                  setShowKeyModal(true);
                }}
                className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold bg-slate-800/60 hover:bg-slate-800 text-slate-200 border border-slate-700/80 transition"
              >
                <div className="flex items-center gap-2.5">
                  <Key className="h-4 w-4 text-amber-400 flex-shrink-0" />
                  <span>X-API-Key Authentication</span>
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                  currentKey
                    ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                    : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                }`}>
                  {currentKey ? 'Configured' : 'Needs Key'}
                </span>
              </button>
            </div>
          </div>
        )}
      </header>

      {/* API Key Configuration Modal */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 text-white shadow-2xl space-y-4">
            <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
              <div className="p-2.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded-xl">
                <Key className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-bold text-base text-slate-100">API Key Authentication</h3>
                <p className="text-xs text-slate-400">Stored safely in browser localStorage (no secret in code)</p>
              </div>
            </div>

            <form onSubmit={handleSaveKey} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  X-API-Key Header Value
                </label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder="Paste authorized API key..."
                    className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 font-mono focus:border-blue-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setApiKeyInput('k5WDnujioTv6IYzKOp8BeSa2lxZhCgMcm3ywUVdJ')}
                    className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-medium border border-slate-700 whitespace-nowrap transition"
                  >
                    Paste Dev Key
                  </button>
                </div>
                <div className="mt-2.5 p-3 rounded-xl bg-slate-950/70 border border-slate-800 text-[11px] text-slate-400 space-y-1">
                  <div className="flex items-center gap-1.5 text-amber-300 font-medium">
                    <ShieldAlert className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>Local Development Key:</span>
                  </div>
                  <p className="font-mono text-slate-300 break-all select-all">
                    k5WDnujioTv6IYzKOp8BeSa2lxZhCgMcm3ywUVdJ
                  </p>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowKeyModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 hover:bg-slate-800 border border-slate-700 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20 transition"
                >
                  Save API Key
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};
