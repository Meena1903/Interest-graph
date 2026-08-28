import React from 'react';
import { Flame, Star, Shield, Clock, MapPin, Activity, ThumbsUp, HelpCircle } from 'lucide-react';

interface ScoreBreakdownProps {
  relevance: number;
  trust: number;
  authority: number;
  freshness: number;
  proximity: number;
  engagementQuality: number;
  spamPenalty: number;
  formula: string;
  postId: number;
}

export const ScoreBreakdown: React.FC<ScoreBreakdownProps> = ({
  relevance,
  trust,
  authority,
  freshness,
  proximity,
  engagementQuality,
  spamPenalty,
  formula,
  postId
}) => {
  const factors = [
    { label: 'Interest Relevance', val: relevance, weight: 0.30, icon: Star, color: 'text-amber-400' },
    { label: 'Author Trust', val: trust, weight: 0.20, icon: Shield, color: 'text-blue-400' },
    { label: 'Domain Authority', val: authority, weight: 0.15, icon: AwardIcon, color: 'text-purple-400' },
    { label: 'Freshness Decay', val: freshness, weight: 0.15, icon: Clock, color: 'text-cyan-400' },
    { label: 'Geographic Proximity', val: proximity, weight: 0.10, icon: MapPin, color: 'text-emerald-400' },
    { label: 'Engagement Quality', val: engagementQuality, weight: 0.05, icon: Activity, color: 'text-rose-400' },
    { label: 'Intent Matching', val: 0.50, weight: 0.05, icon: ThumbsUp, color: 'text-indigo-400' }
  ];

  return (
    <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-5 mt-2 space-y-4 font-sans text-xs">
      <div className="flex items-center justify-between border-b border-slate-850 pb-2">
        <h4 className="font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
          <Flame className="h-3.5 w-3.5 text-emerald-400" />
          Ranking Engine Calculation (Post #{postId})
        </h4>
        <span className="text-[10px] text-slate-500 font-mono">100% Native Python Execution</span>
      </div>

      {/* Grid of factors */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {factors.map((f, i) => {
          const Icon = f.icon;
          const weightedContribution = f.val * f.weight;
          return (
            <div key={i} className="bg-slate-900 border border-slate-850 p-2.5 rounded-md flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Icon className={`h-4 w-4 ${f.color}`} />
                <div>
                  <div className="font-semibold text-slate-300">{f.label}</div>
                  <div className="text-[10px] text-slate-500">Weight: {f.weight * 100}%</div>
                </div>
              </div>
              <div className="text-right">
                <div className="font-mono font-bold text-slate-200">{f.val.toFixed(3)}</div>
                <div className="text-[10px] text-slate-400 font-mono">+{weightedContribution.toFixed(3)}</div>
              </div>
            </div>
          );
        })}
        {spamPenalty > 0 && (
          <div className="bg-red-500/5 border border-red-500/20 p-2.5 rounded-md flex items-center justify-between lg:col-span-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-red-500" />
              <div>
                <div className="font-semibold text-red-400">Spam Risk Penalty</div>
                <div className="text-[10px] text-red-500/60">Deducted from final ranking score</div>
              </div>
            </div>
            <div className="text-right">
              <div className="font-mono font-bold text-red-400">-{spamPenalty.toFixed(3)}</div>
            </div>
          </div>
        )}
      </div>

      {/* Formula Explanation box */}
      <div className="bg-slate-900/60 border border-slate-850 p-3 rounded-md space-y-1.5">
        <div className="font-semibold text-slate-400 flex items-center gap-1">
          <HelpCircle className="h-3.5 w-3.5 text-slate-500" />
          Composite Scoring Formula (Design Doc Section 4):
        </div>
        <div className="font-mono text-emerald-400 bg-slate-950 p-2 rounded border border-slate-900 break-all text-[11px]">
          {formula}
        </div>
      </div>
    </div>
  );
};

// Quick placeholder AwardIcon inside module since it's not exported by lucide
const AwardIcon = (props: any) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <circle cx="12" cy="8" r="7" />
    <polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88" />
  </svg>
);
