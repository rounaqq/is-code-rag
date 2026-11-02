import React, { useState } from 'react';
import { searchISCodes, getStoredApiKey } from '../services/api';
import type { ClauseHit } from '../types/api';
import {
  Search,
  Loader2,
  BookOpen,
  ShieldCheck,
  Key,
  Maximize2,
  Sparkles,
} from 'lucide-react';
import { ClauseInspectorModal } from './rag/ClauseInspectorModal';

// Helper to clean and format clause text cleanly with proper paragraphs and list provisions
const formatClauseText = (text: string, title?: string) => {
  if (!text) return '';
  let cleaned = text.trim();

  // If first line duplicates code + title header, separate or clean it
  const lines = cleaned.split('\n');
  if (
    lines.length > 1 &&
    (lines[0].toLowerCase().includes('clause') ||
      (title && lines[0].toLowerCase().includes(title.toLowerCase().slice(0, 20))))
  ) {
    cleaned = lines.slice(1).join('\n').trim();
  }

  // Normalize common OCR word-join glitches
  cleaned = cleaned
    .replace(/ofarea/gi, 'of area')
    .replace(/ofreinforced/gi, 'of reinforced')
    .replace(/breadthof/gi, 'breadth of')
    .replace(/exteriorjoint/gi, 'exterior joint')
    .replace(/ofbeams/gi, 'of beams')
    .replace(/Splicing ofLongitudinal/gi, 'Splicing of Longitudinal')
    .replace(/>be\b/g, '')
    .trim();

  // Ensure list provisions like a), b), 1), 2) start cleanly on their own line with spacing
  cleaned = cleaned.replace(/([^\n])\s+([a-d]\)|\d+\))\s+/g, '$1\n\n$2 ');

  return cleaned;
};

// Categorized smart prompts
interface PromptCategory {
  id: string;
  name: string;
  queries: Array<{ text: string; label: string; code: string }>;
}

const SMART_PROMPT_CATEGORIES: PromptCategory[] = [
  {
    id: 'all',
    name: 'Featured',
    queries: [
      { text: 'nominal cover for moderate exposure', label: 'Moderate Exposure Cover', code: 'IS 456' },
      { text: 'minimum shear reinforcement stirrups', label: 'Minimum Stirrup Spacing', code: 'IS 456' },
      { text: 'maximum tension reinforcement in a beam', label: 'Max Beam Tension Steel', code: 'IS 456' },
      { text: 'seismic column tie spacing IS 13920', label: 'Column Tie Confinement', code: 'IS 13920' },
      { text: 'isolated footing two-way punching shear', label: 'Punching Shear Perimeter', code: 'IS 456' },
    ],
  },
  {
    id: 'flexure',
    name: 'Flexure & Slabs',
    queries: [
      { text: 'maximum tension reinforcement in a beam', label: 'Max Beam Rebar (4%)', code: 'IS 456' },
      { text: 'two-way slab bending moment coefficients Table 26', label: 'Table 26 Coefficients', code: 'IS 456' },
      { text: 'control of deflection span to effective depth ratio Cl 23.2', label: 'L/d Deflection Limits', code: 'IS 456' },
      { text: 'development length Ld for deformed bars Cl 26.2.1', label: 'Development Length Ld', code: 'IS 456' },
    ],
  },
  {
    id: 'compression',
    name: 'Columns & Ties',
    queries: [
      { text: 'seismic column tie spacing IS 13920', label: 'Ductile Column Ties', code: 'IS 13920' },
      { text: 'short axially loaded column formula Cl 39.3', label: 'Axial Capacity (Pu)', code: 'IS 456' },
      { text: 'minimum eccentricity for columns Cl 25.4', label: 'Min Eccentricity (emin)', code: 'IS 456' },
      { text: 'longitudinal reinforcement in columns limits Cl 26.5.3', label: 'Column Steel (0.8–6%)', code: 'IS 456' },
    ],
  },
  {
    id: 'shear',
    name: 'Shear & Punching',
    queries: [
      { text: 'minimum shear reinforcement stirrups', label: 'Minimum Shear Links', code: 'IS 456' },
      { text: 'design shear strength of concrete Table 19', label: 'Table 19 Shear tau_c', code: 'IS 456' },
      { text: 'isolated footing two-way punching shear', label: 'Footing Punching Shear', code: 'IS 456' },
      { text: 'critical section for shear at distance d from support Cl 40.1', label: 'Critical Section at d', code: 'IS 456' },
    ],
  },
  {
    id: 'seismic',
    name: 'Seismic & Wind',
    queries: [
      { text: 'IS 13920 special confining reinforcement near joints', label: 'Joint Confinement Hoops', code: 'IS 13920' },
      { text: 'IS 1893 seismic zone factor and response reduction R', label: 'Seismic Zone & R Factor', code: 'IS 1893' },
      { text: 'IS 875 Part 3 wind pressure basic wind speed', label: 'Basic Wind Speed Vb', code: 'IS 875' },
    ],
  },
];

export const ISCodeSearch: React.FC = () => {
  const [query, setQuery] = useState('nominal cover for moderate exposure');
  const [standardFilter, setStandardFilter] = useState('ALL');
  const [topK, setTopK] = useState(4);
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<ClauseHit[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Active prompt category
  const [activeCategory, setActiveCategory] = useState<string>('all');

  // Inspect Clause Modal State
  const [inspectingClause, setInspectingClause] = useState<ClauseHit | null>(null);

  const handleSearch = async (searchQuery?: string) => {
    const q = searchQuery || query;
    if (!q.trim()) return;

    const activeKey = getStoredApiKey();
    if (!activeKey) {
      setErrorMsg(
        'API Key required: Multi-standard RAG search requires an authorized X-API-Key header. Please click "Configure API Key" below or the Key button in the navbar.'
      );
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await searchISCodes(q, standardFilter, topK);
      setResults(data.results || []);
    } catch (err: any) {
      if (err.response?.status === 401) {
        setErrorMsg(
          'Unauthorized (401): The provided API key is invalid or not registered in IS_RAG_API_KEYS. Please update your key in the top navigation bar.'
        );
      } else {
        const msg =
          err.response?.data?.detail || err.message || 'Search failed. Please check backend connection and API key.';
        setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const currentCategoryQueries =
    SMART_PROMPT_CATEGORIES.find((c) => c.id === activeCategory)?.queries ||
    SMART_PROMPT_CATEGORIES[0].queries;

  return (
    <div className="space-y-6">
      {/* Search Header Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5 relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 mb-2">
              <BookOpen className="w-3.5 h-3.5" />
              <span>Multi-Standard Legal Corpus</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-100">
              IS Code Legal &amp; Technical RAG Search
            </h1>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl">
              Hybrid search combining BM25 keyword matching, Qdrant dense vector embeddings, and BAAI/bge-reranker-base cross-encoder reranking across 1,535 verified clauses.
            </p>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 self-start sm:self-auto">
            <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span>1,535 Verified Chunks</span>
          </div>
        </div>

        {/* Search Input Bar & Controls */}
        <div className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="h-4 w-4 absolute left-3.5 top-3.5 text-slate-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search engineering provisions, tables, or clause numbers..."
              className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-sans"
            />
          </div>

          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
            {/* Standard Filter */}
            <div className="relative">
              <select
                value={standardFilter}
                onChange={(e) => setStandardFilter(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-blue-500"
              >
                <option value="ALL">All Standards (5 Codes)</option>
                <option value="IS 456">IS 456 (Plain &amp; Reinforced Concrete)</option>
                <option value="IS 13920">IS 13920 (Ductile Detailing)</option>
                <option value="IS 1893">IS 1893 (Earthquake Resistant)</option>
                <option value="IS 800">IS 800 (General Steel)</option>
                <option value="IS 875">IS 875 (Design Loads)</option>
              </select>
            </div>

            {/* Top-K Select */}
            <select
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value))}
              className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-blue-500"
              title="Number of chunks to return"
            >
              <option value={3}>Top 3 Chunks</option>
              <option value={4}>Top 4 Chunks</option>
              <option value={5}>Top 5 Chunks</option>
            </select>

            <button
              onClick={() => handleSearch()}
              disabled={isLoading}
              className="bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:opacity-50 text-white font-semibold px-5 py-2.5 rounded-xl text-xs shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 transition whitespace-nowrap"
            >
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              <span>Search Provisions</span>
            </button>
          </div>
        </div>

        {/* Smart Prompt Suggestions Header & Tabs */}
        <div className="pt-2 border-t border-slate-800/80 space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Smart Engineering Inquiries:</span>
            </span>

            {/* Category Pills */}
            <div className="flex p-0.5 bg-slate-950 rounded-lg border border-slate-800 text-[11px]">
              {SMART_PROMPT_CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={`px-2.5 py-1 rounded font-medium transition ${
                    activeCategory === cat.id
                      ? 'bg-blue-600/30 text-blue-300 font-semibold border border-blue-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {cat.name}
                </button>
              ))}
            </div>
          </div>

          {/* Quick Query Pill Cards */}
          <div className="flex flex-wrap items-center gap-2">
            {currentCategoryQueries.map((sq, i) => (
              <button
                key={i}
                onClick={() => {
                  setQuery(sq.text);
                  handleSearch(sq.text);
                }}
                className="inline-flex items-center gap-1.5 bg-slate-950/80 hover:bg-slate-800/90 text-slate-300 text-xs px-3 py-1.5 rounded-xl border border-slate-800 hover:border-slate-700 transition group shadow-sm"
              >
                <span className="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-1.5 py-0.2 rounded border border-blue-500/20">
                  {sq.code}
                </span>
                <span>{sq.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Error Message */}
      {errorMsg && (
        <div className="bg-rose-950/40 border border-rose-500/40 rounded-2xl p-4 text-rose-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg animate-in fade-in">
          <div>
            <strong className="block text-rose-200 font-semibold mb-0.5">Authentication / Search Error:</strong>
            <span className="text-rose-300/90 leading-relaxed">{errorMsg}</span>
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

      {/* Results Header */}
      {results.length > 0 && (
        <div className="flex items-center justify-between text-xs text-slate-400 px-2 font-mono">
          <span>
            Retrieved <strong className="text-slate-200">{results.length}</strong> governing legal provisions
          </span>
          <span className="text-emerald-400">Reranked via BAAI/bge-reranker-base</span>
        </div>
      )}

      {/* Results List */}
      <div className="space-y-4">
        {results.length === 0 && !isLoading && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-10 text-center shadow-xl space-y-3">
            <BookOpen className="h-10 w-10 mx-auto text-slate-600" />
            <h3 className="font-bold text-slate-200 text-sm">Ready to Search IS Code Corpus</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
              Enter structural keywords, select a standard filter, or click any smart inquiry pill above to retrieve exact clauses.
            </p>
          </div>
        )}

          {results.map((hit, index) => {
            const confidence = hit.confidence_score
              ? Math.round(hit.confidence_score * 100)
              : hit.score
              ? Math.round(hit.score * 100)
              : 85;

            return (
              <div
                key={index}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl hover:border-slate-700 transition space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="bg-blue-600/20 text-blue-400 border border-blue-500/30 font-mono font-bold text-xs px-2.5 py-1 rounded-lg">
                      {hit.chunk_id}
                    </span>
                    <span className="text-xs font-semibold text-slate-200">
                      {hit.code || 'IS 456:2000'}
                    </span>
                    {hit.clause && (
                      <span className="text-xs font-mono text-slate-400">
                        Cl. {hit.clause}
                      </span>
                    )}
                  </div>

                  {/* Actions: Confidence + Inspect Clause Button */}
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-medium text-slate-400 font-mono">Relevance:</span>
                      <div className="w-20 bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
                        <div
                          className="bg-gradient-to-r from-blue-500 to-emerald-400 h-2 rounded-full transition-all duration-500"
                          style={{ width: `${Math.min(confidence, 100)}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono font-bold text-emerald-400">{confidence}%</span>
                    </div>

                    <button
                      onClick={() => setInspectingClause(hit)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold transition"
                      title="Open Clause Deep Inspector Drawer"
                    >
                      <Maximize2 className="w-3 h-3 text-blue-400" />
                      <span>Inspect</span>
                    </button>
                  </div>
                </div>

                {/* Title & Clause Text */}
                <div className="space-y-2.5">
                  <h3 className="font-bold text-sm text-slate-100 tracking-tight">{hit.title}</h3>
                  <div className="bg-slate-950/90 p-4 rounded-xl border border-slate-800 text-slate-200 text-xs sm:text-[13px] leading-relaxed whitespace-pre-line font-sans select-text shadow-inner">
                    {formatClauseText(hit.text, hit.title)}
                  </div>
                </div>

                {/* Footer Citations */}
                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 font-mono border-t border-slate-800/60">
                  <span>Standard: {hit.code || 'IS 456:2000'}</span>
                  {hit.context_path && <span>Context: {hit.context_path}</span>}
                  {hit.page_number && <span>Page: {hit.page_number}</span>}
                </div>
              </div>
            );
          })}
      </div>

      {/* Slide-over Clause Inspector Drawer */}
      <ClauseInspectorModal
        clause={inspectingClause}
        isOpen={!!inspectingClause}
        onClose={() => setInspectingClause(null)}
        onSearchRelated={(relatedQuery) => {
          setInspectingClause(null);
          setQuery(relatedQuery);
          handleSearch(relatedQuery);
        }}
      />
    </div>
  );
};
