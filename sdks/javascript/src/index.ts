/**
 * Skill Fragment Engine - JavaScript/TypeScript SDK
 */

import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

export interface SFEConfig {
  baseURL?: string;
  apiKey?: string;
  timeout?: number;
}

export interface ExecuteRequest {
  task_type: string;
  prompt: string;
  context?: Record<string, any>;
  options?: Record<string, any>;
}

export interface ExecuteResponse {
  decision: 'REUSE' | 'ADAPT' | 'RECOMPUTE';
  result: string;
  metadata: {
    execution_id: string;
    fragment_id?: string;
    cost: number;
    cost_saved: number;
    latency_ms: number;
  };
}

export interface FragmentSearchResult {
  fragment_id: string;
  score: number;
  task_type: string;
}

export interface FeedbackRequest {
  feedback_type: 'positive' | 'negative' | 'neutral';
  score: number;
  fragment_id?: string;
  comment?: string;
}

export interface MetricsResponse {
  total_requests: number;
  reuse_count: number;
  adapt_count: number;
  recompute_count: number;
  hit_rate: number;
  avg_latency_ms: number;
}

export interface PluginInfo {
  name: string;
  state: string;
  type: string;
  version: string;
}

export interface ClusteringResult {
  n_fragments: number;
  n_clusters: number;
  method: string;
  cluster_mapping: Record<string, number>;
}

export interface ShardStats {
  [shardId: number]: {
    count: number;
    fragment_ids: string[];
  };
}

export class SFEClient {
  private client: AxiosInstance;

  constructor(config: SFEConfig = {}) {
    const baseURL = config.baseURL || 'http://localhost:8000';
    const apiKey = config.apiKey || process.env.SFE_API_KEY;
    const timeout = config.timeout || 30000;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (apiKey) {
      headers['Authorization'] = `Bearer ${apiKey}`;
    }

    this.client = axios.create({
      baseURL,
      headers,
      timeout,
    });
  }

  async execute(request: ExecuteRequest): Promise<ExecuteResponse> {
    const response = await this.client.post<ExecuteResponse>('/api/v1/execute', request);
    return response.data;
  }

  async searchFragments(
    query: string,
    topK: number = 10,
    minScore: number = 0.5
  ): Promise<FragmentSearchResult[]> {
    const params = { query, top_k: topK, min_score: minScore };
    const response = await this.client.get<FragmentSearchResult[]>(
      '/api/v1/fragment/search',
      { params }
    );
    return response.data;
  }

  async getFragment(fragmentId: string): Promise<any> {
    const response = await this.client.get(`/api/v1/fragment/${fragmentId}`);
    return response.data;
  }

  async submitFeedback(request: FeedbackRequest): Promise<any> {
    const response = await this.client.post('/api/v1/feedback', request);
    return response.data;
  }

  async getMetrics(): Promise<MetricsResponse> {
    const response = await this.client.get<MetricsResponse>('/api/v1/metrics');
    return response.data;
  }

  async getHealth(): Promise<any> {
    const response = await this.client.get('/api/v1/health');
    return response.data;
  }

  async listPlugins(): Promise<PluginInfo[]> {
    const response = await this.client.get<PluginInfo[]>('/api/v1/plugins');
    return response.data;
  }

  async loadPlugin(name: string, config?: Record<string, any>): Promise<any> {
    const response = await this.client.post(`/api/v1/plugins/${name}/load`, config || {});
    return response.data;
  }

  async unloadPlugin(name: string): Promise<any> {
    const response = await this.client.post(`/api/v1/plugins/${name}/unload`);
    return response.data;
  }

  async runClustering(
    method: string = 'auto',
    taskType?: string
  ): Promise<ClusteringResult> {
    const params: Record<string, string> = { method };
    if (taskType) params.task_type = taskType;
    const response = await this.client.post<ClusteringResult>(
      '/api/v1/clustering/run',
      {},
      { params }
    );
    return response.data;
  }

  async getClusterInfo(taskType?: string): Promise<any[]> {
    const params = taskType ? { task_type: taskType } : {};
    const response = await this.client.get<any[]>('/api/v1/clustering/info', { params });
    return response.data;
  }

  async getVersionHistory(fragmentId: string): Promise<any[]> {
    const response = await this.client.get<any[]>(
      `/api/v1/fragments/${fragmentId}/versions`
    );
    return response.data;
  }

  async rollbackToVersion(
    fragmentId: string,
    version: number,
    reason?: string
  ): Promise<any> {
    const params = reason ? { reason } : {};
    const response = await this.client.post(
      `/api/v1/fragments/${fragmentId}/rollback/${version}`,
      {},
      { params }
    );
    return response.data;
  }

  async getShardingStats(): Promise<ShardStats> {
    const response = await this.client.get<ShardStats>('/api/v1/sharding/stats');
    return response.data;
  }

  async rebalanceShards(numShards: number): Promise<any> {
    const response = await this.client.post(
      `/api/v1/sharding/rebalance?num_shards=${numShards}`
    );
    return response.data;
  }

  async getApiSpec(): Promise<any> {
    const response = await this.client.get('/api/v1/api-spec');
    return response.data;
  }
}

export default SFEClient;
