import React, { useEffect, useState } from 'react';
import { User, RankedPost, RecommendationsResponse } from '../types';
import { apiClient } from '../api/client';
import { FeedCard } from '../components/FeedCard';
import { RecommendationPanel } from '../components/RecommendationPanel';
import { Flame, Compass, RefreshCw, PenTool, Loader2, Sparkles } from 'lucide-react';

interface DashboardProps {
  selectedUser: User | null;
  onInteract: (entityType: string, entityId: number, interactionType: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ selectedUser, onInteract }) => {
  const [feed, setFeed] = useState<RankedPost[]>([]);
  const [recs, setRecs] = useState<RecommendationsResponse | null>(null);
  const [loadingFeed, setLoadingFeed] = useState(false);
  const [loadingRecs, setLoadingRecs] = useState(false);
  
  // Post Creator State
  const [newPostContent, setNewPostContent] = useState('');
  const [newPostTitle, setNewPostTitle] = useState('');
  const [postType, setPostType] = useState('community');
  const [autoTag, setAutoTag] = useState(true);
  const [submittingPost, setSubmittingPost] = useState(false);

  const fetchDashboardData = async () => {
    if (!selectedUser) return;
    
    setLoadingFeed(true);
    setLoadingRecs(true);
    
    try {
      const feedRes = await apiClient.getFeed(selectedUser.id);
      setFeed(feedRes.feed);
      
      const recsRes = await apiClient.getRecommendations(selectedUser.id);
      setRecs(recsRes);
    } catch (err) {
      console.error("Dashboard fetch error:", err);
    } finally {
      setLoadingFeed(false);
      setLoadingRecs(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [selectedUser]);

  const handleCreatePost = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser || !newPostContent.trim()) return;

    setSubmittingPost(true);
    try {
      await apiClient.createPost({
        title: newPostTitle || undefined,
        content: newPostContent,
        post_type: postType,
        author_id: selectedUser.id,
        auto_tag: autoTag
      });
      
      setNewPostTitle('');
      setNewPostContent('');
      // Refresh feed
      fetchDashboardData();
    } catch (err) {
      console.error("Post creation error:", err);
      alert("Failed to create post. Verify if backend server is running.");
    } finally {
      setSubmittingPost(false);
    }
  };

  const handleInteractionWithRefresh = async (entityType: string, entityId: number, interactionType: string) => {
    await onInteract(entityType, entityId, interactionType);
    // Refresh recommendations/feed dynamically to see weight updates!
    setTimeout(() => {
      fetchDashboardData();
    }, 500);
  };

  if (!selectedUser) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* Left 2 Columns: Feed & Creator */}
      <div className="lg:col-span-2 space-y-6">
        {/* Creator Panel */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
          <h2 className="text-md font-bold text-slate-100 mb-4 flex items-center gap-2">
            <PenTool className="h-5 w-5 text-emerald-400" />
            Share something with the community
          </h2>
          <form onSubmit={handleCreatePost} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input
                type="text"
                placeholder="Title (optional)"
                value={newPostTitle}
                onChange={(e) => setNewPostTitle(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
              <select
                value={postType}
                onChange={(e) => setPostType(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
              >
                <option value="community">Community Post</option>
                <option value="business">Commercial/Ad Post</option>
                <option value="event_promo">Event Promotion</option>
              </select>
            </div>
            <textarea
              placeholder="What are you working on? (NVIDIA NIM Llama 3.1 will extract interest tags automatically)"
              rows={3}
              value={newPostContent}
              onChange={(e) => setNewPostContent(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
              required
            />
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-xs text-slate-400 select-none cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoTag}
                  onChange={(e) => setAutoTag(e.target.checked)}
                  className="rounded border-slate-800 bg-slate-950 text-emerald-500 focus:ring-0"
                />
                <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
                Auto-extract interests using NVIDIA LLM
              </label>
              <button
                type="submit"
                disabled={submittingPost}
                className="bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-800 text-slate-950 px-5 py-2 rounded-lg font-bold text-xs flex items-center gap-2 transition-all shadow-lg shadow-emerald-950/20"
              >
                {submittingPost ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Publish'}
              </button>
            </div>
          </form>
        </div>

        {/* Feed Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-emerald-400" />
            <h2 className="font-bold text-lg text-slate-100">Personalized Feed</h2>
          </div>
          <button 
            onClick={fetchDashboardData}
            className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
          >
            <RefreshCw className={`h-4 w-4 ${loadingFeed ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Feed Posts */}
        {loadingFeed ? (
          <div className="space-y-4">
            {[1, 2].map((i) => (
              <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-6 h-40 animate-pulse" />
            ))}
          </div>
        ) : feed.length === 0 ? (
          <div className="text-center py-12 text-slate-500 bg-slate-900/30 rounded-xl border border-dashed border-slate-800">
            No content found in your feed. Join some clubs or select more interests in onboarding to start!
          </div>
        ) : (
          <div className="space-y-4">
            {feed.map((rankedPost) => (
              <FeedCard
                key={rankedPost.post.id}
                rankedPost={rankedPost}
                onInteract={handleInteractionWithRefresh}
              />
            ))}
          </div>
        )}
      </div>

      {/* Right Column: Recommendations Panel */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-sm text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <Compass className="h-4 w-4 text-slate-500" /> Discovery Panel
          </h2>
        </div>
        <RecommendationPanel 
          recommendations={recs}
          loading={loadingRecs}
          onInteract={handleInteractionWithRefresh}
        />
      </div>
    </div>
  );
};
