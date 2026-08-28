const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

import {
  FeedResponse,
  GraphResponse,
  RecommendationsResponse,
  SystemMetrics,
  User,
  UserProfile,
  Post
} from '../types';

export const apiClient = {
  async getUsers(): Promise<User[]> {
    const response = await fetch(`${API_BASE_URL}/users`);
    if (!response.ok) throw new Error('Failed to fetch users');
    return response.json();
  },

  async getUserProfile(userId: number): Promise<UserProfile> {
    const response = await fetch(`${API_BASE_URL}/users/${userId}`);
    if (!response.ok) throw new Error(`Failed to fetch user profile for ${userId}`);
    return response.json();
  },

  async createUser(user: {
    username: string;
    display_name: string;
    email: string;
    bio?: string;
    location_city?: string;
    location_lat?: number;
    location_lon?: number;
    user_type: string;
    interest_ids: number[];
  }): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(user)
    });
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Failed to create user');
    }
    return response.json();
  },

  async createPost(post: {
    title?: string;
    content: string;
    post_type: string;
    author_id: number;
    interest_ids?: number[];
    auto_tag: boolean;
  }): Promise<Post> {
    const response = await fetch(`${API_BASE_URL}/posts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(post)
    });
    if (!response.ok) throw new Error('Failed to create post');
    return response.json();
  },

  async getFeed(userId: number, limit = 10): Promise<FeedResponse> {
    const response = await fetch(`${API_BASE_URL}/feed/${userId}?limit=${limit}`);
    if (!response.ok) throw new Error(`Failed to fetch feed for user ${userId}`);
    return response.json();
  },

  async getRecommendations(userId: number, limit = 5): Promise<RecommendationsResponse> {
    const response = await fetch(`${API_BASE_URL}/recommendations/${userId}?limit=${limit}`);
    if (!response.ok) throw new Error(`Failed to fetch recommendations for user ${userId}`);
    return response.json();
  },

  async getGraph(userId: number, depth = 2): Promise<GraphResponse> {
    const response = await fetch(`${API_BASE_URL}/graph/${userId}?depth=${depth}`);
    if (!response.ok) throw new Error(`Failed to fetch graph for user ${userId}`);
    return response.json();
  },

  async getMetrics(): Promise<SystemMetrics> {
    const response = await fetch(`${API_BASE_URL}/metrics`);
    if (!response.ok) throw new Error('Failed to fetch metrics');
    return response.json();
  },

  async recordInteraction(interaction: {
    user_id: number;
    entity_type: string;
    entity_id: number;
    interaction_type: string;
  }): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/interactions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(interaction)
    });
    if (!response.ok) throw new Error('Failed to record interaction');
    return response.json();
  }
};
