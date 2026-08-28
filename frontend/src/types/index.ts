export interface Domain {
  id: number;
  name: string;
  description?: string;
  icon?: string;
}

export interface Interest {
  id: number;
  name: string;
  domain_id: number;
  parent_interest_id?: number;
  description?: string;
}

export interface User {
  id: number;
  username: string;
  display_name: string;
  email: string;
  bio?: string;
  location_city?: string;
  user_type: string;
  is_verified: boolean;
  trust_score: number;
  interaction_count: number;
  created_at: string;
  interests?: Interest[];
}

export interface UserProfile extends User {
  interest_vector?: number[];
  interest_vector_labels?: string[];
}

export interface Post {
  id: number;
  title?: string;
  content: string;
  media_url?: string;
  post_type: string;
  author_id: number;
  club_id?: number;
  view_count: number;
  like_count: number;
  comment_count: number;
  share_count: number;
  save_count: number;
  authority_score: number;
  engagement_quality_score: number;
  spam_risk_score: number;
  llm_tagged: boolean;
  llm_tag_model?: string;
  llm_tag_latency_ms?: number;
  is_flagged: boolean;
  created_at: string;
  interests: Interest[];
}

export interface RankedPost {
  post: Post;
  author?: User;
  final_score: number;
  relevance: number;
  trust: number;
  authority: number;
  freshness: number;
  proximity: number;
  engagement_quality: number;
  intent_match: number;
  spam_risk_penalty: number;
  diversity_boost: boolean;
  score_formula: string;
}

export interface FeedResponse {
  user_id: number;
  is_cold_start: boolean;
  total_candidates: number;
  returned_count: number;
  feed: RankedPost[];
  generated_at: string;
  feed_strategy: string;
}

export interface RecommendedItem {
  entity_type: string;
  entity_id: number;
  name: string;
  score: number;
  reason: string;
}

export interface RecommendationsResponse {
  user_id: number;
  clubs: RecommendedItem[];
  businesses: RecommendedItem[];
  events: RecommendedItem[];
  people: RecommendedItem[];
  generated_at: string;
}

export interface GraphNode {
  id: string;
  label: string;
  node_type: string;
  trust_score?: number;
  properties?: Record<string, any>;
}

export interface GraphEdge {
  source: string;
  target: string;
  edge_type: string;
  weight: number;
  properties?: Record<string, any>;
}

export interface GraphResponse {
  user_id: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  depth: number;
  node_count: number;
  edge_count: number;
}

export interface SystemMetrics {
  total_users: number;
  total_posts: number;
  total_clubs: number;
  total_businesses: number;
  total_events: number;
  total_interactions: number;
  avg_trust_score: number;
  avg_feed_relevance: number;
  cold_start_users: number;
  llm_calls_today: number;
  generated_at: string;
}
