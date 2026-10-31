import React, { useEffect, useState, useCallback } from 'react';
import { 
  Activity, 
  Clock, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Key, 
  BarChart3, 
  ShieldCheck, 
  Database, 
  Search 
} from 'lucide-react';
import { getAuditSummary } from '../services/api';
import type { AuditSummaryData } from '../types/api';

export const AuditDashboard: React.FC = () => {
  const [data, setData] = useState<AuditSummaryData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(() => new Date());

  const fetchSummary = useCallback(async () => {
    try {
      const res = await getAuditSummary(200);
      setData(res);
      setError(null);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch audit telemetry.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    getAuditSummary(200)
      .then((res) => {
        if (!ignore) {
          setData(res);
          setError(null);
          setLastRefreshed(new Date());
          setLoading(false);
        }
      })
      .catch((err: any) => {
        if (!ignore) {
          setError(err.response?.data?.detail || err.message || 'Failed to fetch audit telemetry.');
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, []);

  // Handle auto-refresh interval
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchSummary();
    }, 8000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchSummary]);

  // Compute success rate
  const totalQueries = data?.total_queries_logged || 0;
  const statusCodes = data?.status_code_distribution || {};
  const successCount = statusCodes['200'] || 0;
  const successRate = totalQueries > 0 ? ((successCount / totalQueries) * 100).toFixed(1) : '100.0';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-3">
              <Activity className="w-3.5 h-3.5" />
              Step 10 Telemetry & Observability
            </div>
            <h1 className="text-2xl font-bold text-slate-100">
              Audit & Production Observability Dashboard
            </h1>
            <p className="text-sm text-slate-400 mt-1 max-w-2xl">
              Live telemetry aggregated from <code className="text-emerald-400 font-mono">data/audit/audit.jsonl</code>.
              Tracks query volumes, latency distributions, clause frequencies, and security authentications.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs font-medium text-slate-300 bg-slate-950 px-3 py-2 rounded-xl border border-slate-800 cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-3.5 h-3.5 rounded text-blue-600 bg-slate-900 border-slate-700"
              />
              Auto-refresh (8s)
            </label>

            <button
              onClick={() => {
                setLoading(true);
                fetchSummary();
              }}
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 transition-colors border border-slate-700 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
          <span>Endpoint: <code className="text-slate-400 font-mono">GET /v1/audit/summary</code></span>
          <span>Last polled: {lastRefreshed.toLocaleTimeString()}</span>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-xs text-red-300 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <span>Error loading observability metrics: {error}</span>
        </div>
      )}

      {/* Top 4 KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Queries */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
            <span>Total Logged Queries</span>
            <Database className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-3xl font-black text-slate-100 font-mono">
            {totalQueries.toLocaleString()}
          </div>
          <p className="text-[11px] text-slate-500 mt-2">
            Audit trail records preserved
          </p>
        </div>

        {/* p50 / p95 Latency */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
            <span>Latency Percentiles</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-100 font-mono">
              {data?.latency_statistics_ms?.median_p50 ?? 0}
            </span>
            <span className="text-xs font-mono text-slate-400">ms (p50)</span>
          </div>
          <div className="flex items-center gap-3 text-[11px] text-slate-400 mt-2 font-mono">
            <span>Avg: <strong className="text-slate-300">{data?.latency_statistics_ms?.average ?? 0}ms</strong></span>
            <span>p95: <strong className="text-amber-400">{data?.latency_statistics_ms?.p95 ?? 0}ms</strong></span>
          </div>
        </div>

        {/* Success Rate */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
            <span>API Success Rate</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-black text-emerald-400 font-mono">
            {successRate}%
          </div>
          <p className="text-[11px] text-slate-500 mt-2 font-mono">
            {successCount} of {totalQueries} requests HTTP 200
          </p>
        </div>

        {/* Authorized Keys */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
            <span>Authorized Key Callers</span>
            <Key className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-3xl font-black text-slate-100 font-mono">
            {data?.unique_authorized_keys?.length || 1}
          </div>
          <div className="text-[11px] text-slate-400 mt-2 truncate font-mono">
            {data?.unique_authorized_keys?.join(', ') || 'dev_user'}
          </div>
        </div>
      </div>

      {/* Main Grid: Status Code Distribution & Top Retrieved Clauses */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Top Retrieved IS Clauses (7 cols) */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-blue-400" />
              Most Frequently Retrieved IS Clauses
            </h2>
            <span className="text-xs font-mono text-slate-500">Top 10 Chunks</span>
          </div>

          {data?.top_retrieved_clauses && data.top_retrieved_clauses.length > 0 ? (
            <div className="space-y-3">
              {data.top_retrieved_clauses.map((item, idx) => {
                const maxCount = data.top_retrieved_clauses![0].retrieval_count || 1;
                const pct = Math.round((item.retrieval_count / maxCount) * 100);
                return (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="text-slate-300 truncate max-w-sm" title={item.clause_id}>
                        {item.clause_id}
                      </span>
                      <span className="text-blue-400 font-bold ml-2">
                        {item.retrieval_count} hits
                      </span>
                    </div>
                    <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
                      <div
                        className="bg-gradient-to-r from-blue-600 to-indigo-500 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-10 text-center text-xs text-slate-500">
              No clause retrieval events recorded yet. Run a search query in IS Code Search to populate.
            </div>
          )}
        </div>

        {/* Right Column: Status Code Distribution & Security Audit (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Status Breakdown */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2 border-b border-slate-800 pb-3">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              HTTP Response Status Codes
            </h2>

            <div className="space-y-2.5">
              {Object.entries(statusCodes).map(([code, count]) => {
                const is2xx = code.startsWith('2');
                const is4xx = code.startsWith('4');
                const pillColor = is2xx
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : is4xx
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                  : 'bg-red-500/10 text-red-400 border-red-500/20';

                return (
                  <div key={code} className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded font-bold border ${pillColor}`}>
                        {code}
                      </span>
                      <span className="text-slate-300">
                        {is2xx ? 'OK / Validated' : is4xx ? 'Client Error / Rejected' : 'Server Exception'}
                      </span>
                    </div>
                    <span className="font-bold text-slate-100">{count} calls</span>
                  </div>
                );
              })}

              {Object.keys(statusCodes).length === 0 && (
                <div className="py-6 text-center text-xs text-slate-500">
                  No status code records found.
                </div>
              )}
            </div>
          </div>

          {/* Security & Access Audit Info */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Key className="w-3.5 h-3.5 text-blue-400" />
              Access Control & Rate Safeguards
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Every request is authenticated via SHA-256 hashed API key validation. All queries, IP headers, and response latencies are written append-only to disk.
            </p>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[11px] text-slate-400 space-y-1">
              <div><span className="text-slate-500">LOG ROTATION:</span> JSON Lines (JSONL)</div>
              <div><span className="text-slate-500">TAMPER SEAL:</span> Append-Only Write Lock</div>
              <div><span className="text-slate-500">AUDIT RETENTION:</span> Full Project Lifecycle</div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Queries Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2 border-b border-slate-800 pb-3">
          <Search className="w-4 h-4 text-indigo-400" />
          Recent Request Log (Last 5 Entries)
        </h2>

        {data?.recent_queries && data.recent_queries.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-2 font-medium">Timestamp</th>
                  <th className="pb-2 font-medium">Caller</th>
                  <th className="pb-2 font-medium">Query / Operation</th>
                  <th className="pb-2 font-medium">Top Retrieved Clause</th>
                  <th className="pb-2 font-medium">Latency</th>
                  <th className="pb-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data.recent_queries.map((q, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30">
                    <td className="py-2.5 text-slate-400 whitespace-nowrap">
                      {q.timestamp ? new Date(q.timestamp).toLocaleTimeString() : 'N/A'}
                    </td>
                    <td className="py-2.5 text-blue-400 whitespace-nowrap">
                      {q.key_name || 'system'}
                    </td>
                    <td className="py-2.5 text-slate-200 max-w-xs truncate" title={q.query}>
                      {q.query || '-'}
                    </td>
                    <td className="py-2.5 text-slate-400 max-w-xs truncate" title={q.top_clause || ''}>
                      {q.top_clause || 'none'}
                    </td>
                    <td className="py-2.5 text-amber-400 whitespace-nowrap">
                      {q.latency_ms !== undefined ? `${q.latency_ms} ms` : '-'}
                    </td>
                    <td className="py-2.5 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        q.status_code === 200 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                      }`}>
                        {q.status_code || 200}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-slate-500">
            No recent query records found.
          </div>
        )}
      </div>
    </div>
  );
};
