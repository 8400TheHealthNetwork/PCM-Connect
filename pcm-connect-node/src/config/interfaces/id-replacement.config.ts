export interface IdReplacementConfig {
  mode: 'mock' | 'http';
  baseUrl: string;
  endpoint: string;
  timeoutMs: number;
}
