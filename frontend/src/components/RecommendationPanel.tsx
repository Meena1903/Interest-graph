import React from 'react';
import { RecommendationsResponse } from '../types';
import { Users, Compass, Briefcase, Calendar, Plus, UserPlus, ArrowRight } from 'lucide-react';

interface RecommendationPanelProps {
  recommendations: RecommendationsResponse | null;
  loading: boolean;
  onInteract: (entityType: string, entityId: number, interactionType: string) => void;
}

export const RecommendationPanel: React.FC<RecommendationPanelProps> = ({
  recommendations,
  loading,
  onInteract
}) => {
  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4 animate-pulse">
        <div className="h-4 bg-slate-800 rounded w-1/3" />
        <div className="space-y-3">
          <div className="h-10 bg-slate-800 rounded" />
          <div className="h-10 bg-slate-800 rounded" />
          <div className="h-10 bg-slate-800 rounded" />
        </div>
      </div>
    );
  }

  if (!recommendations) return null;

  const sections = [
    {
      title: 'Suggested Clubs',
      items: recommendations.clubs,
      icon: Compass,
      btnIcon: Plus,
      action: 'rsvp',
      emptyText: 'No club recommendations available.'
    },
    {
      title: 'People You May Know',
      items: recommendations.people,
      icon: Users,
      btnIcon: UserPlus,
      action: 'like', // simulate follow action
      emptyText: 'No people recommendations found.'
    },
    {
      title: 'Local Businesses',
      items: recommendations.businesses,
      icon: Briefcase,
      btnIcon: ArrowRight,
      action: 'contact_click',
      emptyText: 'No vendor recommendations.'
    },
    {
      title: 'Upcoming Events',
      items: recommendations.events,
      icon: Calendar,
      btnIcon: Plus,
      action: 'rsvp',
      emptyText: 'No matching events.'
    }
  ];

  return (
    <div className="space-y-6">
      {sections.map((sec, idx) => {
        const HeaderIcon = sec.icon;
        return (
          <div key={idx} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider flex items-center gap-2 border-b border-slate-800 pb-2">
              <HeaderIcon className="h-4 w-4 text-emerald-400" />
              {sec.title}
            </h3>

            {sec.items.length === 0 ? (
              <div className="text-xs text-slate-500 py-2">{sec.emptyText}</div>
            ) : (
              <div className="space-y-3">
                {sec.items.map((item, itemIdx) => {
                  const BtnIcon = sec.btnIcon;
                  return (
                    <div 
                      key={itemIdx}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/40 border border-slate-850 hover:border-slate-800 transition-all text-xs"
                    >
                      <div className="space-y-0.5 max-w-[70%]">
                        <div className="font-semibold text-slate-200 truncate">{item.name}</div>
                        <div className="text-[10px] text-slate-400 line-clamp-1">{item.reason}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[10px] text-emerald-400 bg-emerald-950/20 px-1.5 py-0.5 rounded border border-emerald-900/30">
                          {item.score.toFixed(2)}
                        </span>
                        <button
                          onClick={() => onInteract(item.entity_type, item.entity_id, sec.action)}
                          className="p-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
                        >
                          <BtnIcon className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
