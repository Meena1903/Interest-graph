import React from 'react';
import { Award, Shield, UserCheck, Flame } from 'lucide-react';

interface TrustBadgeProps {
  trustScore: number;
  userType: string;
}

export const TrustBadge: React.FC<TrustBadgeProps> = ({ trustScore, userType }) => {
  // Determine color coding based on trust range
  let colorClass = 'bg-slate-800 text-slate-400 border-slate-700';
  let label = 'Unverified';
  let Icon = Shield;

  if (userType === 'verified' || userType === 'business') {
    colorClass = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    label = userType === 'business' ? 'Business Partner' : 'Verified';
    Icon = UserCheck;
  } else if (trustScore >= 0.75) {
    colorClass = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    label = `High Trust (${(trustScore * 10).toFixed(1)})`;
    Icon = Award;
  } else if (trustScore >= 0.50) {
    colorClass = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20';
    label = `Trusted (${(trustScore * 10).toFixed(1)})`;
    Icon = Shield;
  } else if (trustScore < 0.30) {
    colorClass = 'bg-rose-500/10 text-rose-400 border-rose-500/20';
    label = `Low Trust (${(trustScore * 10).toFixed(1)})`;
    Icon = Flame;
  }

  return (
    <div
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-semibold tracking-wide uppercase ${colorClass}`}
      title={`Trust Score (propagated PageRank): ${trustScore.toFixed(3)}`}
    >
      <Icon className="h-3 w-3" />
      {label}
    </div>
  );
};
