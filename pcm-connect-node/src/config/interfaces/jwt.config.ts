export interface JwtConfig {
  issuer: string;
  audience: string;
  expirySeconds: number;
  signingKeyPath: string;
  algorithm: 'ES256' | 'RS256';
}
