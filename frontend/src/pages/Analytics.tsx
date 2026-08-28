import React, { useEffect, useState } from 'react';
import { SystemMetrics } from '../types';
import { apiClient } from '../api/client';
import { BarChart2, Shield, Users, FileText, Activity, Compass, Calendar, Award } from 'lucide-react';

export const Analytics: React.FC = () => {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchMetrics = async () => {
      setLoading(true);
      try {
        const res = await apiClient.getMetrics();
        setMetrics(res);
      } catch (err) {
        console.error("Fetch metrics error:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchMetrics();
  }, []);

  if (loading) {
    return (
      <div className="flex h-60 items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500" />
      </div>
    );
  }

  if (!metrics) return null;

  const cardData = [
    { label: 'Total Node Users', val: metrics.total_users, desc: 'Persona nodes in database', icon: Users, color: 'text-emerald-400' },
    { label: 'Total Post Nodes', val: metrics.total_posts, desc: 'Published feed elements', icon: FileText, color: 'text-cyan-400' },
    { label: 'Clubs', val: metrics.total_clubs, desc: 'Active community groups', icon: Compass, color: 'text-pink-400' },
    { label: 'Verified Businesses', val: metrics.total_businesses, desc: 'Commercial platform members', icon: Shield, color: 'text-orange-400' },
    { label: 'Events Hosted', val: metrics.total_events, desc: 'Gatherings with location tags', icon: Calendar, color: 'text-purple-400' },
    { label: 'Total Interactions', val: metrics.total_interactions, desc: 'Signal edges in graph', icon: Activity, color: 'text-rose-400' }
  ];

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800 pb-3">
        <h2 className="font-bold text-lg text-slate-100 flex items-center gap-2">
          <BarChart2 className="h-5 w-5 text-emerald-400" />
          Graph Analytics & Performance
        </h2>
      </div>

      {/* Grid of stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {cardData.map((c, i) => {
          const Icon = c.icon;
          return (
            <div key={i} className="bg-slate-900 border border-slate-800 p-6 rounded-xl flex items-center justify-between shadow-lg">
              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">{c.label}</span>
                <span className="text-3xl font-extrabold text-slate-100 block font-mono">{c.val}</span>
                <span className="text-[10px] text-slate-500 block">{c.desc}</span>
              </div>
              <div className={`p-3 rounded-lg bg-slate-950/40 border border-slate-800 ${c.color}`}>
                <Icon className="h-6 w-6" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Engine Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4 shadow-lg">
          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider flex items-center gap-2 border-b border-slate-800 pb-2">
            <Award className="h-4 w-4 text-emerald-400" />
            Ranking Engine Health
          </h3>
          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-850">
              <span className="text-slate-400">Mean Trust Score (PageRank)</span>
              <span className="font-mono text-emerald-400 font-bold">{metrics.avg_trust_score.toFixed(3)}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-850">
              <span className="text-slate-400">Cold-start Active Users</span>
              <span className="font-mono text-slate-200 font-bold">{metrics.cold_start_users} / {metrics.total_users}</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-400">Average Feed Relevance</span>
              <span className="font-mono text-cyan-400 font-bold">{(metrics.avg_feed_relevance * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4 shadow-lg">
          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider flex items-center gap-2 border-b border-slate-800 pb-2">
            <Shield className="h-4 w-4 text-cyan-400" />
            NVIDIA NIM API Metadata
          </h3>
          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-850">
              <span className="text-slate-400">NLP Tagging Model</span>
              <span className="font-mono text-cyan-400 font-bold">Llama-3.1-70b-instruct</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-850">
              <span className="text-slate-400">Semantic Embedding Model</span>
              <span className="font-mono text-slate-200 font-bold">nv-embedqa-e5-v5</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-400">LLM Tagged Posts</span>
              <span className="font-mono text-emerald-400 font-bold">{metrics.llm_calls_today} posts</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
