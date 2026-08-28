import React, { useEffect, useRef } from 'react';
import { GraphResponse } from '../types';
import { Network } from 'vis-network';

interface GraphVisualizationProps {
  graphData: GraphResponse | null;
  loading: boolean;
}

export const GraphVisualization: React.FC<GraphVisualizationProps> = ({
  graphData,
  loading
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);

  useEffect(() => {
    if (!containerRef.current || !graphData || loading) return;

    // Convert nodes to vis format
    const visNodes = graphData.nodes.map((node) => {
      let color = '#334155'; // default slate-700
      let shape = 'dot';
      let value = 15;

      if (node.node_type === 'user') {
        color = '#10b981'; // emerald-500
        shape = 'diamond';
        value = 25;
      } else if (node.node_type === 'interest') {
        color = '#f59e0b'; // amber-500
        shape = 'dot';
        value = 20;
      } else if (node.node_type === 'domain') {
        color = '#8b5cf6'; // violet-500
        shape = 'square';
        value = 28;
      } else if (node.node_type === 'club') {
        color = '#ec4899'; // pink-500
        shape = 'triangle';
        value = 20;
      } else if (node.node_type === 'business') {
        color = '#f97316'; // orange-500
        shape = 'triangleDown';
        value = 20;
      } else if (node.node_type === 'event') {
        color = '#06b6d4'; // cyan-500
        shape = 'star';
        value = 18;
      } else if (node.node_type === 'post') {
        color = '#64748b'; // slate-500
        shape = 'dot';
        value = 12;
      }

      return {
        id: node.id,
        label: node.label,
        color: {
          background: color,
          border: '#0f172a',
          highlight: {
            background: color,
            border: '#ffffff'
          }
        },
        shape: shape,
        size: value,
        font: {
          color: '#cbd5e1',
          size: 11,
          face: 'sans-serif'
        }
      };
    });

    // Convert edges to vis format
    const visEdges = graphData.edges.map((edge) => {
      let color = '#475569'; // default slate-600
      let dashes = false;

      if (edge.edge_type === 'SIMILAR_TO') {
        color = '#e2e8f0'; // light gray
        dashes = true;
      } else if (edge.edge_type === 'HAS_INTEREST') {
        color = '#34d399'; // light green
      } else if (edge.edge_type === 'ENGAGED_WITH') {
        color = '#f87171'; // red
      }

      return {
        from: edge.source,
        to: edge.target,
        label: edge.edge_type,
        color: {
          color: color,
          highlight: '#ffffff'
        },
        dashes: dashes,
        arrows: {
          to: { enabled: true, scaleFactor: 0.5 }
        },
        font: {
          size: 8,
          color: '#64748b',
          strokeWidth: 0
        },
        width: Math.max(1, edge.weight * 3)
      };
    });

    const data = {
      nodes: visNodes,
      edges: visEdges
    };

    const options = {
      physics: {
        stabilization: true,
        barnesHut: {
          gravitationalConstant: -2000,
          centralGravity: 0.3,
          springLength: 95,
          springConstant: 0.04,
          damping: 0.09,
          avoidOverlap: 0.2
        }
      },
      interaction: {
        hover: true,
        tooltipDelay: 300
      }
    };

    // Initialize network
    networkRef.current = new Network(containerRef.current, data, options);

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, [graphData, loading]);

  if (loading) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl h-[500px] flex items-center justify-center flex-col gap-3">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500" />
        <span className="text-sm text-slate-400">Loading graph explorer...</span>
      </div>
    );
  }

  return (
    <div className="relative bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Legend overlay */}
      <div className="absolute top-4 left-4 bg-slate-950/80 border border-slate-850 p-3 rounded-lg z-10 text-[10px] space-y-1.5 flex flex-col backdrop-blur-sm">
        <div className="font-bold text-slate-400 uppercase tracking-wider mb-0.5">Legend</div>
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-500" /> User Node</div>
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-amber-500" /> Interest Tag</div>
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-purple-500" /> Top Domain</div>
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-pink-500" /> Community Club</div>
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-orange-500" /> Commercial Biz</div>
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-cyan-500" /> Event</div>
      </div>
      
      {/* vis container */}
      <div ref={containerRef} className="h-[500px] w-full" />
    </div>
  );
};
