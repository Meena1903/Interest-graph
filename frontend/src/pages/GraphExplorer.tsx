import React, { useEffect, useState } from 'react';
import { User, GraphResponse } from '../types';
import { apiClient } from '../api/client';
import { GraphVisualization } from '../components/GraphVisualization';
import { Network, RefreshCw, Layers } from 'lucide-react';

interface GraphExplorerProps {
  selectedUser: User | null;
}

export const GraphExplorer: React.FC<GraphExplorerProps> = ({ selectedUser }) => {
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [depth, setDepth] = useState(2);
  const [loading, setLoading] = useState(false);

  const fetchGraph = async () => {
    if (!selectedUser) return;
    setLoading(true);
    try {
      const res = await apiClient.getGraph(selectedUser.id, depth);
      setGraphData(res);
    } catch (err) {
      console.error("Fetch graph error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, [selectedUser, depth]);

  if (!selectedUser) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Network className="h-5 w-5 text-emerald-400" />
          <h2 className="font-bold text-lg text-slate-100">Interest Graph Explorer</h2>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1">
            <Layers className="h-3.5 w-3.5 text-slate-400" />
            <select
              value={depth}
              onChange={(e) => setDepth(parseInt(e.target.value))}
              className="bg-transparent border-none text-xs text-slate-200 focus:ring-0 cursor-pointer p-0"
            >
              <option value="1">1 Hop (Direct)</option>
              <option value="2">2 Hops (Standard)</option>
              <option value="3">3 Hops (Deep)</option>
            </select>
          </div>
          <button 
            onClick={fetchGraph}
            className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="bg-slate-900/40 p-4 rounded-xl border border-slate-800 text-xs text-slate-400 flex items-center justify-between">
        <div>
          Interactive BFS neighborhood mapping centered around <span className="text-emerald-400 font-semibold">{selectedUser.display_name}</span>. Nodes represent entities and edges represent weighted interactions.
        </div>
        {graphData && (
          <div className="font-mono text-[10px] text-slate-500 bg-slate-950 px-2 py-0.5 rounded border border-slate-850">
            Nodes: {graphData.node_count} | Edges: {graphData.edge_count}
          </div>
        )}
      </div>

      <GraphVisualization graphData={graphData} loading={loading} />
    </div>
  );
};
