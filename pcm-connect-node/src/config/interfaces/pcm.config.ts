export interface PcmConfig {
  introspectionMode: 'pcm' | 'mock';
  baseUrl: string;
  tokenEndpoint: string;
  introspectionEndpoint: string;
  metadataEndpoint: string;
  clientId: string;
  clientCertThumbprint: string;
  resource?: string;
  clientTokenCacheEnabled: boolean;
  clientTokenCacheSafetyMarginSeconds: number;
  mtls: {
    certPath: string;
    keyPath: string;
    caCertPath: string;
    tlsServername?: string;
  };
  clientAssertion: {
    privateKeyPath: string;
    audience: string;
    algorithm: 'ES256' | 'RS256';
  };
}
