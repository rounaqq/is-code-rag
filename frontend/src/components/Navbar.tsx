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
      <header className="bg-slate-950/80 backdrop-blur-xl border-b border-white/[0.06] text-white sticky top-0 z-50 shadow-lg shadow-black/25">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-3">
            {/* Brand Logo & Title */}
            <div
              className="flex items-center gap-3 cursor-pointer select-none flex-shrink-0 group"
              onClick={() => handleTabClick('dashboard')}
            >
              <div className="relative">
                <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl blur-sm opacity-40 group-hover:opacity-80 transition duration-300" />
                <div className="relative bg-gradient-to-br from-slate-900 via-blue-950 to-indigo-950 p-2 rounded-xl text-white border border-blue-500/30 shadow-md shadow-blue-500/10 flex-shrink-0">
                  <Compass className="h-5 w-5 text-blue-400 group-hover:rotate-45 group-hover:text-blue-300 transition-all duration-300" />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-black text-base sm:text-lg tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent group-hover:from-white group-hover:to-blue-200 transition-all whitespace-nowrap">
                  Build More AI
                </span>
                <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/25 font-mono tracking-wider uppercase shadow-sm whitespace-nowrap">
                  v2.0
                </span>
              </div>
            </div>

            {/* Desktop Navigation Links - Segmented Glass Capsule Dock */}
            <nav className="hidden lg:flex items-center gap-1 bg-slate-900/60 p-1 rounded-2xl border border-slate-800/80 backdrop-blur-md shadow-inner flex-shrink-0">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleTabClick(item.id)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all duration-200 flex-shrink-0 btn-tactile cursor-pointer ${
                      isActive
                        ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md shadow-blue-600/30 border border-blue-400/20'
                        : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50'
                    }`}
                  >
                    <Icon className={`h-3.5 w-3.5 flex-shrink-0 transition-colors ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-slate-200'}`} />
                    <span className="hidden xl:inline">{item.label}</span>
                    <span className="xl:hidden">{item.shortLabel}</span>
                  </button>
                );
              })}
            </nav>

            {/* Right Status Controls - Consistent Heights & Harmonized Pills */}
            <div className="flex items-center gap-2 flex-shrink-0">
              {/* Backend Heartbeat Pill */}
              <div
                className={`h-8 px-3 rounded-full text-[11px] font-mono font-medium border flex items-center gap-2 transition-all flex-shrink-0 shadow-sm ${
                  isHealthy === true
                    ? 'bg-emerald-950/50 border-emerald-500/30 text-emerald-300 shadow-emerald-500/5'
                    : isHealthy === false
                    ? 'bg-rose-950/50 border-rose-500/30 text-rose-300'
                    : 'bg-slate-900/80 border-slate-800 text-slate-400'
                }`}
                title={isHealthy ? 'FastAPI Backend Live on port 8000' : 'FastAPI Backend Disconnected'}
              >
                <span className="relative flex h-2 w-2 flex-shrink-0">
                  {isHealthy === true && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  )}
                  <span
                    className={`relative inline-flex rounded-full h-2 w-2 ${
                      isHealthy === true
                        ? 'bg-emerald-400'
                        : isHealthy === false
                        ? 'bg-rose-400'
                        : 'bg-slate-500'
                    }`}
                  />
                </span>
                <span className="whitespace-nowrap">
                  {isHealthy === true ? 'API Live' : isHealthy === false ? 'Offline' : 'Connecting'}
                </span>
              </div>

              {/* API Key Modal Button */}
              <button
                onClick={() => {
                  setApiKeyInput(getStoredApiKey());
                  setShowKeyModal(true);
                }}
                className={`h-8 px-3 rounded-full text-[11px] font-mono font-medium border flex items-center gap-1.5 transition-all flex-shrink-0 btn-tactile cursor-pointer shadow-sm ${
                  currentKey
                    ? 'bg-slate-900/90 hover:bg-slate-800/90 text-slate-200 border-slate-700/80 hover:border-amber-500/40 shadow-sm'
                    : 'bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border-amber-500/35'
                }`}
                title="Configure X-API-Key"
              >
                <span className="relative flex h-2 w-2 flex-shrink-0">
                  {currentKey && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-60"></span>
                  )}
                  <span
                    className={`relative inline-flex rounded-full h-2 w-2 ${
                      currentKey ? 'bg-amber-400' : 'bg-slate-500'
                    }`}
                  />
                </span>
                <Key className="h-3 w-3 text-amber-400 flex-shrink-0" />
                <span className="whitespace-nowrap">
                  {currentKey ? 'Key Active' : 'Set API Key'}
                </span>
              </button>

              {/* Mobile / Tablet Menu Toggle */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="lg:hidden p-2 rounded-xl bg-slate-900 text-slate-300 hover:text-white border border-slate-800 transition flex-shrink-0"
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
