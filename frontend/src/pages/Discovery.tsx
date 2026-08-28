import React, { useEffect, useState } from 'react';
import { User, RecommendationsResponse } from '../types';
import { apiClient } from '../api/client';
import { RecommendationPanel } from '../components/RecommendationPanel';
import { Compass, RefreshCw } from 'lucide-react';

interface DiscoveryProps {
  selectedUser: User | null;
  onInteract: (entityType: string, entityId: number, interactionType: string) => void;
}

export const Discovery: React.FC<DiscoveryProps> = ({ selectedUser, onInteract }) => {
  const [recs, setRecs] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchRecommendations = async () => {
    if (!selectedUser) return;
    setLoading(true);
    try {
      const res = await apiClient.getRecommendations(selectedUser.id, 8);
      setRecs(res);
    } catch (err) {
      console.error("Recommendations error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, [selectedUser]);

  const handleInteractionWithRefresh = async (entityType: string, entityId: number, interactionType: string) => {
    await onInteract(entityType, entityId, interactionType);
    // Refresh page to see new similarity scores
    setTimeout(() => {
      fetchRecommendations();
    }, 500);
  };

  if (!selectedUser) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Compass className="h-5 w-5 text-emerald-400" />
          <h2 className="font-bold text-lg text-slate-100">Explore & Discover</h2>
        </div>
        <button 
          onClick={fetchRecommendations}
          className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <RecommendationPanel 
          recommendations={recs}
          loading={loading}
          onInteract={handleInteractionWithRefresh}
        />
      </div>
    </div>
  );
};
