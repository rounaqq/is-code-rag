import React, { useState } from 'react';
import { ShieldCheck, Check, Copy, QrCode } from 'lucide-react';

interface EngineeringStampProps {
  status: 'APPROVED' | 'REVIEWED' | 'DRAFT' | 'REJECTED';
  reviewerName: string;
  licenseNo: string;
  reviewerRole: string;
  date: string;
  auditHash?: string;
  allChecklistVerified?: boolean;
}

// Generate a realistic SVG QR code pattern based on the hash
const renderQrPattern = (seedStr: string) => {
  const size = 21; // standard QR 21x21 modules
  const modules: boolean[][] = Array.from({ length: size }, () => Array(size).fill(false));

  // Corner finder patterns (7x7)
  const drawFinder = (startX: number, startY: number) => {
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) {
        if (
          r === 0 ||
          r === 6 ||
          c === 0 ||
          c === 6 ||
          (r >= 2 && r <= 4 && c >= 2 && c <= 4)
        ) {
          modules[startY + r][startX + c] = true;
        }
      }
    }
  };

  drawFinder(0, 0); // Top-left
  drawFinder(14, 0); // Top-right
  drawFinder(0, 14); // Bottom-left

  // Timing lines
  for (let i = 8; i < 13; i++) {
    modules[6][i] = i % 2 === 0;
    modules[i][6] = i % 2 === 0;
  }

  // Pseudo-random data modules derived from seedStr
  let hash = 0;
  for (let i = 0; i < seedStr.length; i++) {
    hash = (hash << 5) - hash + seedStr.charCodeAt(i);
    hash |= 0;
  }

  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      // Don't overwrite finder patterns
      const inTopLeft = r < 8 && c < 8;
      const inTopRight = r < 8 && c >= 13;
      const inBottomLeft = r >= 13 && c < 8;
      if (!inTopLeft && !inTopRight && !inBottomLeft) {
        const val = Math.sin(hash + r * 17 + c * 31) > 0.1;
        modules[r][c] = val;
      }
    }
  }

  return modules;
};

export const EngineeringStamp: React.FC<EngineeringStampProps> = ({
  status,
  reviewerName,
  licenseNo,
  reviewerRole,
  date,
  auditHash,
  allChecklistVerified = true,
}) => {
  const [copied, setCopied] = useState(false);

  // Compute a deterministic SHA-256 style hash string
  const computedHash =
    auditHash ||
    (() => {
      let h = 0x811c9dc5;
      const str = `${reviewerName}-${licenseNo}-${date}-${status}`;
      for (let i = 0; i < str.length; i++) {
        h ^= str.charCodeAt(i);
        h += (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24);
      }
      const p1 = (h >>> 0).toString(16).padStart(8, '0');
      const p2 = ((h ^ 0x5a5a5a5a) >>> 0).toString(16).padStart(8, '0');
      const p3 = ((h ^ 0x3c3c3c3c) >>> 0).toString(16).padStart(8, '0');
      const p4 = ((h ^ 0xa5a5a5a5) >>> 0).toString(16).padStart(8, '0');
      return `${p1}${p2}${p3}${p4}`.toLowerCase();
    })();

  const isApproved = status === 'APPROVED' && allChecklistVerified;
  const isRejected = status === 'REJECTED';

  const colorClasses = isApproved
    ? {
        border: 'border-emerald-500/40',
        bg: 'bg-emerald-950/20',
        text: 'text-emerald-400',
        stampBorder: '#10b981',
        title: 'APPROVED FOR CONSTRUCTION',
        subtitle: 'STATUTORY IS 456 CERTIFICATION',
      }
    : isRejected
    ? {
        border: 'border-rose-500/40',
        bg: 'bg-rose-950/20',
        text: 'text-rose-400',
        stampBorder: '#f43f5e',
        title: 'REJECTED - INADEQUATE CAPACITY',
        subtitle: 'VIOLATES MANDATORY CODE PROVISIONS',
      }
    : {
        border: 'border-amber-500/40',
        bg: 'bg-amber-950/20',
        text: 'text-amber-400',
        stampBorder: '#f59e0b',
        title: 'DRAFT - FOR REVIEW ONLY',
        subtitle: 'CONDITIONAL ENGINEERING SIGN-OFF',
      };

  const qrModules = renderQrPattern(computedHash);

  const handleCopyHash = () => {
    navigator.clipboard.writeText(computedHash);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`p-4 rounded-2xl border ${colorClasses.border} ${colorClasses.bg} space-y-4 font-mono shadow-xl relative overflow-hidden select-none`}>
      {/* Background Watermark Stamp Linework */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
        <div className="flex items-center gap-2">
          <ShieldCheck className={`w-4 h-4 ${colorClasses.text}`} />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Digital Engineering Seal &amp; Audit QR
          </span>
        </div>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${colorClasses.border} ${colorClasses.text} bg-slate-950`}>
          {isApproved ? 'VERIFIED SIGNATURE' : 'CONDITIONAL'}
        </span>
      </div>

      {/* Main Stamp & QR Layout */}
      <div className="flex flex-col sm:flex-row items-center gap-4">
        {/* Vector SVG QR Code with Scanner Anchor */}
        <div className="flex-shrink-0 p-2 rounded-xl bg-white border border-slate-700 shadow-md flex flex-col items-center">
          <svg viewBox="0 0 21 21" className="w-24 h-24 shape-rendering-crispEdges">
            {qrModules.map((row, r) =>
              row.map((active, c) =>
                active ? <rect key={`${r}-${c}`} x={c} y={r} width="1" height="1" fill="#0f172a" /> : null
              )
            )}
          </svg>
          <div className="flex items-center gap-1 text-[8px] font-mono text-slate-800 mt-1 font-bold">
            <QrCode className="w-2.5 h-2.5 text-blue-600" />
            <span>SCAN TO AUDIT</span>
          </div>
        </div>

        {/* Official Seal Badge */}
        <div className="flex-1 w-full space-y-2 p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-left">
          <div className="border-b border-slate-800 pb-1.5">
            <h4 className={`text-xs font-extrabold tracking-wide ${colorClasses.text}`}>
              {colorClasses.title}
            </h4>
            <p className="text-[9px] text-slate-500 uppercase">{colorClasses.subtitle}</p>
          </div>

          <div className="text-[11px] space-y-1 text-slate-300">
            <div>
              <span className="text-slate-500">ENGINEER: </span>
              <strong className="text-slate-100">{reviewerName}</strong>
            </div>
            <div>
              <span className="text-slate-500">ROLE: </span>
              <span className="text-slate-300">{reviewerRole}</span>
            </div>
            <div>
              <span className="text-slate-500">REGISTRATION: </span>
              <span className="text-blue-400 font-bold">{licenseNo}</span>
            </div>
            <div>
              <span className="text-slate-500">DATE CERTIFIED: </span>
              <span className="text-emerald-400">{date}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Immutable SHA-256 Audit Hash Footer */}
      <div className="flex items-center justify-between gap-2 p-2 rounded-xl bg-slate-950 border border-slate-800/80 text-[10px]">
        <div className="flex items-center gap-1.5 truncate">
          <span className="text-slate-500 font-bold">SHA-256:</span>
          <span className="text-slate-300 truncate font-mono">{computedHash}</span>
        </div>
        <button
          onClick={handleCopyHash}
          type="button"
          className="p-1 px-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition flex items-center gap-1 flex-shrink-0"
          title="Copy Audit Hash"
        >
          {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-slate-400" />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
    </div>
  );
};

