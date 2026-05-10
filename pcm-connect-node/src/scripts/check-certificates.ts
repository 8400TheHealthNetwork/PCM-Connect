/**
 * Safe certificate and key diagnostics script
 * Checks key types and algorithm compatibility without printing sensitive data
 */
import 'dotenv/config'; // Load .env file
import { createPrivateKey } from 'crypto';
import { readFile, access, constants } from 'fs/promises';

interface KeyDiagnostic {
  label: string;
  envVar: string;
  path: string;
  exists: boolean;
  readable: boolean;
  asymmetricKeyType?: string;
  namedCurve?: string;
  error?: string;
}

async function checkKey(
  label: string,
  envVar: string,
  path: string | undefined,
): Promise<KeyDiagnostic> {
  const diagnostic: KeyDiagnostic = {
    label,
    envVar,
    path: path || '(not configured)',
    exists: false,
    readable: false,
  };

  if (!path || path === '') {
    diagnostic.error = 'Path not configured';
    return diagnostic;
  }

  // Check if file exists and is readable
  try {
    await access(path, constants.R_OK);
    diagnostic.exists = true;
    diagnostic.readable = true;
  } catch (error) {
    diagnostic.error = `File not accessible: ${error instanceof Error ? error.message : 'unknown error'}`;
    return diagnostic;
  }

  // Read and analyze key (do NOT print key contents)
  try {
    const keyData = await readFile(path, 'utf-8');
    const privateKey = createPrivateKey(keyData);

    diagnostic.asymmetricKeyType = privateKey.asymmetricKeyType;

    // For EC keys, get the named curve
    if (privateKey.asymmetricKeyType === 'ec') {
      const keyObject = privateKey.export({ format: 'jwk' }) as any;
      diagnostic.namedCurve = keyObject.crv;
    }
  } catch (error) {
    diagnostic.error = `Failed to parse key: ${error instanceof Error ? error.message : 'unknown error'}`;
  }

  return diagnostic;
}

function checkAlgorithmCompatibility(
  keyType: string | undefined,
  namedCurve: string | undefined,
  algorithm: string,
): { compatible: boolean; reason?: string } {
  if (!keyType) {
    return { compatible: false, reason: 'Key type unknown' };
  }

  switch (algorithm) {
    case 'ES256':
      if (keyType !== 'ec') {
        return {
          compatible: false,
          reason: `ES256 requires EC key, but key type is ${keyType}`,
        };
      }
      if (namedCurve && namedCurve !== 'P-256') {
        return {
          compatible: false,
          reason: `ES256 requires P-256 curve, but key uses ${namedCurve}`,
        };
      }
      return { compatible: true };

    case 'RS256':
      if (keyType !== 'rsa') {
        return {
          compatible: false,
          reason: `RS256 requires RSA key, but key type is ${keyType}`,
        };
      }
      return { compatible: true };

    default:
      return {
        compatible: false,
        reason: `Unsupported algorithm: ${algorithm}`,
      };
  }
}

async function checkCertificates() {
  console.log('Certificate and Key Diagnostics');
  console.log('================================\n');

  // Get environment variables
  const pcmMtlsKeyPath = process.env.PCM_MTLS_KEY_PATH;
  const pcmClientAssertionKeyPath =
    process.env.PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH;
  const jwtSigningKeyPath = process.env.JWT_SIGNING_KEY_PATH;
  const pcmClientAssertionAlgorithm =
    process.env.PCM_CLIENT_ASSERTION_ALGORITHM || 'ES256';

  // Check keys
  const keys: KeyDiagnostic[] = [
    await checkKey('PCM mTLS Key', 'PCM_MTLS_KEY_PATH', pcmMtlsKeyPath),
    await checkKey(
      'PCM Client Assertion Key',
      'PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH',
      pcmClientAssertionKeyPath,
    ),
    await checkKey(
      'JWT Signing Key',
      'JWT_SIGNING_KEY_PATH',
      jwtSigningKeyPath,
    ),
  ];

  // Print diagnostics
  for (const key of keys) {
    console.log(`${key.label}:`);
    console.log(`  Env Var:    ${key.envVar}`);
    console.log(`  Path:       ${key.path}`);
    console.log(`  Exists:     ${key.exists ? 'Yes' : 'No'}`);
    console.log(`  Readable:   ${key.readable ? 'Yes' : 'No'}`);

    if (key.asymmetricKeyType) {
      console.log(`  Key Type:   ${key.asymmetricKeyType}`);
      if (key.namedCurve) {
        console.log(`  Curve:      ${key.namedCurve}`);
      }
    }

    if (key.error) {
      console.log(`  Error:      ${key.error}`);
    }

    console.log();
  }

  // Check client assertion algorithm compatibility
  console.log('PCM Client Assertion Configuration:');
  console.log(`  Algorithm:  ${pcmClientAssertionAlgorithm}`);

  const assertionKey = keys.find(
    (k) => k.envVar === 'PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH',
  );
  if (assertionKey && assertionKey.asymmetricKeyType) {
    const compat = checkAlgorithmCompatibility(
      assertionKey.asymmetricKeyType,
      assertionKey.namedCurve,
      pcmClientAssertionAlgorithm,
    );

    console.log(`  Compatible: ${compat.compatible ? 'Yes' : 'No'}`);
    if (compat.reason) {
      console.log(`  Note:       ${compat.reason}`);
    }
  } else {
    console.log(`  Compatible: Cannot determine (key not loaded)`);
  }

  console.log();

  // Summary and recommendations
  console.log('Summary:');
  console.log('────────────────────────────────────────────────');

  const allReadable = keys.every((k) => k.readable);
  const assertionCompatible =
    assertionKey &&
    assertionKey.asymmetricKeyType &&
    checkAlgorithmCompatibility(
      assertionKey.asymmetricKeyType,
      assertionKey.namedCurve,
      pcmClientAssertionAlgorithm,
    ).compatible;

  if (allReadable && assertionCompatible) {
    console.log('✓ All certificates readable and compatible');
  } else {
    console.log('✗ Issues detected:');
    keys.forEach((k) => {
      if (!k.readable) {
        console.log(`  - ${k.label}: ${k.error || 'Not readable'}`);
      }
    });

    if (!assertionCompatible && assertionKey) {
      const compat = checkAlgorithmCompatibility(
        assertionKey.asymmetricKeyType,
        assertionKey.namedCurve,
        pcmClientAssertionAlgorithm,
      );
      console.log(`  - PCM Client Assertion: ${compat.reason}`);
    }
  }

  console.log();

  // Additional Configuration
  const tlsServername = process.env.PCM_TLS_SERVERNAME;
  if (tlsServername) {
    console.log('TLS Configuration:');
    console.log(`  Servername Override: ${tlsServername}`);
    console.log('  (Used for SNI when URL hostname differs from certificate SAN)');
    console.log();
  }

  // Recommendations
  if (
    assertionKey &&
    assertionKey.asymmetricKeyType === 'rsa' &&
    pcmClientAssertionAlgorithm === 'ES256'
  ) {
    console.log('Recommendation:');
    console.log('  Your PCM client assertion key is RSA, but algorithm is ES256.');
    console.log('  Options:');
    console.log('  1. Set PCM_CLIENT_ASSERTION_ALGORITHM=RS256 in .env');
    console.log('  2. Obtain an EC P-256 key from PCM/Certificate team');
    console.log();
  }

  process.exit(allReadable && assertionCompatible ? 0 : 1);
}

void checkCertificates();
