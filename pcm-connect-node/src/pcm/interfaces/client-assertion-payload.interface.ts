/**
 * JWT payload for OAuth2 client assertion
 */
export interface ClientAssertionPayload {
  iss: string; // Issuer - client ID
  sub: string; // Subject - client ID
  aud: string; // Audience - token endpoint URL
  iat: number; // Issued at (Unix timestamp)
  exp: number; // Expires at (Unix timestamp)
  jti: string; // JWT ID (UUID)
}
