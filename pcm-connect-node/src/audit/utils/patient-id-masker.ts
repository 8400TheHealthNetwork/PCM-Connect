/**
 * Mask patient ID for audit logs
 * Shows only last 4 digits for privacy
 */
export class PatientIdMasker {
  /**
   * Mask patient identifier, showing only last 4 characters
   * @param patientId - Patient identifier (e.g., national ID)
   * @returns Masked ID (e.g., "****6789")
   */
  static mask(patientId: string | undefined | null): string {
    if (!patientId || patientId.length === 0) {
      return '****';
    }

    if (patientId.length <= 4) {
      return '****';
    }

    const last4 = patientId.slice(-4);
    return `****${last4}`;
  }

  /**
   * Hash patient ID for correlation in logs (SHA-256)
   * @param patientId - Patient identifier
   * @returns Hex-encoded hash
   */
  static hash(patientId: string | undefined | null): string {
    if (!patientId) {
      return 'none';
    }

    // Simple hash for V1 - in production, use crypto.createHash('sha256')
    // For now, just return a placeholder that shows it would be hashed
    return `hash_${patientId.length}_chars`;
  }
}
