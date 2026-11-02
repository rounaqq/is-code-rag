import React from 'react';
import { CheckCircle2, AlertCircle, ShieldCheck } from 'lucide-react';

export interface ChecklistItem {
  id: string;
  label: string;
  code: string;
  checked: boolean;
  required: boolean;
  clause: string;
}

interface DeficiencyChecklistProps {
  items: ChecklistItem[];
  onToggle: (id: string) => void;
}

export const DeficiencyChecklist: React.FC<DeficiencyChecklistProps> = ({ items, onToggle }) => {
  const verifiedCount = items.filter((it) => it.checked).length;
  const totalCount = items.length;
  const allVerified = verifiedCount === totalCount;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3 font-sans">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
            Mandatory Statutory Deficiency Checklist
          </h3>
        </div>
        <span
          className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded-full border ${
            allVerified
              ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
              : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
          }`}
        >
          {verifiedCount} / {totalCount} Verified
        </span>
      </div>

      <p className="text-[11px] text-slate-400 leading-relaxed">
        Verify that all critical limit-state and seismic safety provisions are satisfied before applying the official engineering seal:
      </p>

      <div className="space-y-2 pt-1">
        {items.map((item) => (
          <label
            key={item.id}
            className={`flex items-start gap-3 p-2.5 rounded-xl border cursor-pointer transition ${
              item.checked
                ? 'bg-slate-950/70 border-slate-800 hover:border-slate-700'
                : 'bg-amber-950/20 border-amber-500/30 hover:border-amber-500/50'
            }`}
          >
            <input
              type="checkbox"
              checked={item.checked}
              onChange={() => onToggle(item.id)}
              className="mt-0.5 w-4 h-4 rounded text-blue-600 bg-slate-950 border-slate-700 focus:ring-0 cursor-pointer"
            />
            <div className="flex-1 space-y-0.5 select-none">
              <div className="flex items-center justify-between">
                <span className={`text-xs font-semibold ${item.checked ? 'text-slate-200' : 'text-amber-200'}`}>
                  {item.label}
                </span>
                <span className="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-1.5 py-0.2 rounded border border-blue-500/20">
                  {item.code}
                </span>
              </div>
              <p className="text-[10px] text-slate-400 leading-normal font-mono">
                {item.clause}
              </p>
            </div>
            {item.checked ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
            )}
          </label>
        ))}
      </div>
    </div>
  );
};

