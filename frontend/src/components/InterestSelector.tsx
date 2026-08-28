import React from 'react';
import { Interest } from '../types';
import { Check } from 'lucide-react';

interface InterestSelectorProps {
  availableInterests: Interest[];
  selectedIds: number[];
  onChange: (ids: number[]) => void;
}

export const InterestSelector: React.FC<InterestSelectorProps> = ({
  availableInterests,
  selectedIds,
  onChange
}) => {
  const handleToggle = (id: number) => {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((x) => x !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
      {availableInterests.map((interest) => {
        const isSelected = selectedIds.includes(interest.id);
        return (
          <button
            key={interest.id}
            type="button"
            onClick={() => handleToggle(interest.id)}
            className={`flex items-center justify-between p-3 rounded-lg border text-left text-xs font-semibold transition-all ${
              isSelected
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-md shadow-emerald-950/20'
                : 'bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700/80 hover:bg-slate-850'
            }`}
          >
            <div>
              <div>{interest.name}</div>
              {interest.description && (
                <div className="text-[10px] text-slate-500 font-normal mt-0.5 line-clamp-1">
                  {interest.description}
                </div>
              )}
            </div>
            {isSelected && (
              <div className="h-4 w-4 bg-emerald-500 rounded-full flex items-center justify-center text-slate-950 ml-2 flex-shrink-0">
                <Check className="h-3 w-3 stroke-[3]" />
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
};
