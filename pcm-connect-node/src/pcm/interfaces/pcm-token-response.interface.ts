/**
 * OAuth2 token response from PCM
 */
export interface PcmTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * Cached token with expiration tracking
 */
export interface CachedToken {
  access_token: string;
  token_type: string;
  expires_at: number; // Unix timestamp (seconds)
}
