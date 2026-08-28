import React, { useState } from 'react';
import { RankedPost } from '../types';
import { Heart, MessageSquare, Share2, Bookmark, Flame, Award, ChevronDown, ChevronUp } from 'lucide-react';
import { TrustBadge } from './TrustBadge';
import { ScoreBreakdown } from './ScoreBreakdown';

interface FeedCardProps {
  rankedPost: RankedPost;
  onInteract: (entityType: string, entityId: number, interactionType: string) => void;
}

export const FeedCard: React.FC<FeedCardProps> = ({ rankedPost, onInteract }) => {
  const { post, author, final_score, relevance, trust, authority, freshness, proximity, engagement_quality, diversity_boost, score_formula } = rankedPost;
  const [showScoreDetails, setShowScoreDetails] = useState(false);
  const [liked, setLiked] = useState(false);
  const [saved, setSaved] = useState(false);
  const [commentsCount, setCommentsCount] = useState(post.comment_count);
  const [likesCount, setLikesCount] = useState(post.like_count);

  const handleLike = () => {
    if (!liked) {
      setLikesCount(prev => prev + 1);
      setLiked(true);
      onInteract('post', post.id, 'like');
    }
  };

  const handleSave = () => {
    if (!saved) {
      setSaved(true);
      onInteract('post', post.id, 'save');
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 hover:border-slate-700/80 transition-all shadow-lg flex flex-col gap-4 relative overflow-hidden">
      {/* Diversity Boost Badge */}
      {diversity_boost && (
        <div className="absolute top-0 right-0 bg-gradient-to-l from-cyan-500/20 to-transparent text-cyan-400 text-[10px] font-bold px-3 py-1 uppercase tracking-wider border-l border-b border-cyan-500/30">
          MMR Diversity Pick
        </div>
      )}

      {/* Author and Post Type Meta */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-slate-800 flex items-center justify-center font-bold text-slate-300 border border-slate-700 uppercase">
            {author?.username?.substring(0, 2) || 'P'}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-100">{author?.display_name || 'Anonymous Post'}</span>
              {author && <TrustBadge trustScore={author.trust_score} userType={author.user_type} />}
            </div>
            <span className="text-xs text-slate-400">@{author?.username || 'anonymous'}</span>
          </div>
        </div>
        
        {/* Post Type Tag */}
        <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium border ${
          post.post_type === 'business'
            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
            : post.post_type === 'event_promo'
            ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
        }`}>
          {post.post_type}
        </span>
      </div>

      {/* Post Content */}
      <div className="space-y-2">
        {post.title && <h3 className="text-md font-bold text-slate-100">{post.title}</h3>}
        <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{post.content}</p>
        
        {post.media_url && (
          <div className="mt-3 rounded-lg overflow-hidden border border-slate-800 max-h-60 bg-slate-950 flex items-center justify-center">
            <img src={post.media_url} alt="Post media" className="object-contain w-full h-full" />
          </div>
        )}
      </div>

      {/* Interests list */}
      <div className="flex flex-wrap gap-1.5 mt-1">
        {post.interests.map((interest) => (
          <span key={interest.id} className="text-[11px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded-md hover:bg-slate-700 cursor-pointer">
            #{interest.name}
          </span>
        ))}
        {post.llm_tagged && (
          <span className="text-[10px] text-cyan-400 self-center flex items-center gap-1 font-mono" title={`Tagged by NVIDIA NIM: ${post.llm_tag_model} (${post.llm_tag_latency_ms?.toFixed(0)}ms)`}>
            <Award className="h-3 w-3" /> NIM Tagged
          </span>
        )}
      </div>

      {/* Divider */}
      <div className="h-px bg-slate-850 w-full" />

      {/* Engagement Actions and Rank Score Selector */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          <button 
            onClick={handleLike}
            className={`flex items-center gap-1.5 text-xs font-medium transition-colors ${
              liked ? 'text-red-500' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Heart className={`h-4 w-4 ${liked ? 'fill-current' : ''}`} />
            {likesCount}
          </button>
          
          <button 
            onClick={() => {
              setCommentsCount(c => c + 1);
              onInteract('post', post.id, 'comment');
            }}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            <MessageSquare className="h-4 w-4" />
            {commentsCount}
          </button>

          <button 
            onClick={() => onInteract('post', post.id, 'share')}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            <Share2 className="h-4 w-4" />
            Share
          </button>

          <button 
            onClick={handleSave}
            className={`flex items-center gap-1.5 text-xs font-medium transition-colors ${
              saved ? 'text-blue-400' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Bookmark className={`h-4 w-4 ${saved ? 'fill-current' : ''}`} />
            {saved ? 'Saved' : 'Save'}
          </button>
        </div>

        {/* Explainable Rank Score Button */}
        <button
          onClick={() => {
            setShowScoreDetails(!showScoreDetails);
            onInteract('post', post.id, 'view');
          }}
          className="flex items-center gap-1 text-xs font-semibold text-emerald-400 hover:text-emerald-300 transition-colors bg-emerald-500/10 px-3 py-1 rounded-lg border border-emerald-500/20"
        >
          <Flame className="h-3.5 w-3.5" />
          Score: {final_score.toFixed(3)}
          {showScoreDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>
      </div>

      {/* Detailed Math/Scoring Breakdown */}
      {showScoreDetails && (
        <ScoreBreakdown 
          relevance={relevance}
          trust={trust}
          authority={authority}
          freshness={freshness}
          proximity={proximity}
          engagementQuality={engagement_quality}
          spamPenalty={rankedPost.spam_risk_penalty}
          formula={score_formula}
          postId={post.id}
        />
      )}
    </div>
  );
};
