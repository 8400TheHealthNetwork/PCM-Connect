import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { InternalJwtService } from './internal-jwt.service';
import { generateKeyPair, type KeyLike } from 'jose';
import { jwtVerify } from 'jose';
import { CreateJwtInput } from './interfaces/jwt-payload.interface';

describe('InternalJwtService', () => {
  let service: InternalJwtService;
  let testPrivateKey: KeyLike;
  let testPublicKey: KeyLike;

  beforeAll(async () => {
    // Generate test RS256 key pair once for all tests (matching default algorithm)
    const keyPair = await generateKeyPair('RS256');
    testPrivateKey = keyPair.privateKey;
    testPublicKey = keyPair.publicKey;
  });

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        InternalJwtService,
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn((key: string, defaultValue?: any) => {
              const config: Record<string, any> = {
                'jwt.issuer': 'test-adapter',
                'jwt.audience': 'https://fhir.test.example.com',
                'jwt.expirySeconds': 60,
                'jwt.signingKeyPath': '', // Empty in tests, we'll mock the key
                'jwt.algorithm': 'RS256', // Default to RS256 for tests
              };
              return config[key] !== undefined ? config[key] : defaultValue;
            }),
          },
        },
      ],
    }).compile();

    service = module.get<InternalJwtService>(InternalJwtService);

    // Set mock private key to avoid file system access in tests
    service.setMockPrivateKey(testPrivateKey);
  });

  describe('createJwt', () => {
    it('should successfully create and sign a JWT', async () => {
      const input: CreateJwtInput = {
        serviceProviderId: 'provider-123',
        localPatientId: 'patient-456',
        scope: 'fhir.read patient/*.read',
        correlationId: 'corr-789',
      };

      const jwt = await service.createJwt(input);

      expect(jwt).toBeDefined();
      expect(typeof jwt).toBe('string');
      expect(jwt.split('.')).toHaveLength(3); // header.payload.signature
    });

    it('should include all required claims in JWT', async () => {
      const input: CreateJwtInput = {
        serviceProviderId: 'provider-123',
        localPatientId: 'patient-456',
        scope: 'fhir.read patient/*.read',
        correlationId: 'corr-789',
      };

      const jwt = await service.createJwt(input);

      // Verify JWT and check claims
      const { payload } = await jwtVerify(jwt, testPublicKey);

      expect(payload.iss).toBe('test-adapter');
      expect(payload.sub).toBe('provider-123');
      expect(payload.aud).toBe('https://fhir.test.example.com');
      expect(payload.patient).toBe('patient-456');
      expect(payload.scope).toBe('fhir.read patient/*.read');
      expect(payload.correlation_id).toBe('corr-789');
      expect(payload.iat).toBeDefined();
      expect(payload.exp).toBeDefined();
    });

    it('should set expiry time correctly', async () => {
      const input: CreateJwtInput = {
        serviceProviderId: 'provider-123',
        localPatientId: 'patient-456',
        scope: 'fhir.read',
      };

      const beforeCreate = Math.floor(Date.now() / 1000);
      const jwt = await service.createJwt(input);
      const afterCreate = Math.floor(Date.now() / 1000);

      const { payload } = await jwtVerify(jwt, testPublicKey);

      expect(payload.exp).toBeDefined();
      expect(payload.iat).toBeDefined();

      const iat = payload.iat as number;
      const exp = payload.exp as number;

      // Expiry should be 60 seconds after issued
      expect(exp - iat).toBe(60);

      // Issued at should be around now
      expect(iat).toBeGreaterThanOrEqual(beforeCreate);
      expect(iat).toBeLessThanOrEqual(afterCreate);
    });

    it('should use configured issuer', async () => {
      const input: CreateJwtInput = {
        serviceProviderId: 'provider-123',
        localPatientId: 'patient-456',
        scope: 'fhir.read',
      };

      const jwt = await service.createJwt(input);
      const { payload } = await jwtVerify(jwt, testPublicKey);

      expect(payload.iss).toBe('test-adapter');
    });

    it('should use configured audience', async () => {
      const input: CreateJwtInput = {
        serviceProviderId: 'provider-123',
        localPatientId: 'patient-456',
        scope: 'fhir.read',
      };

      const jwt = await service.createJwt(input);
      const { payload } = await jwtVerify(jwt, testPublicKey);

      expect(payload.aud).toBe('https://fhir.test.example.com');
    });

    it('should omit correlation_id if not provided', async () => {
      const input: CreateJwtInput = {
        serviceProviderId: 'provider-123',
        localPatientId: 'patient-456',
        scope: 'fhir.read',
        // No correlationId
      };

      const jwt = await service.createJwt(input);
      const { payload } = await jwtVerify(jwt, testPublicKey);

      expect(payload.correlation_id).toBeUndefined();
    });

    it('should throw error if signing key is not loaded', async () => {
      // Create service without mock key
      const moduleWithoutKey: TestingModule = await Test.createTestingModule({
        providers: [
          InternalJwtService,
          {
            provide: ConfigService,
            useValue: {
              get: jest.fn((key: string, defaultValue?: any) => {
                const config: Record<string, any> = {
                  'jwt.issuer': 'test-adapter',
                  'jwt.audience': 'https://fhir.test.example.com',
                  'jwt.expirySeconds': 60,
                  'jwt.signingKeyPath': '',
                };
                return config[key] !== undefined ? config[key] : defaultValue;
              }),
            },
          },
        ],
      }).compile();

      const serviceWithoutKey = moduleWithoutKey.get<InternalJwtService>(
        InternalJwtService,
      );
      // Don't set mock key

      const input: CreateJwtInput = {
        serviceProviderId: 'provider-123',
        localPatientId: 'patient-456',
        scope: 'fhir.read',
      };

      await expect(serviceWithoutKey.createJwt(input)).rejects.toThrow(
        'JWT signing key not loaded',
      );
    });

    it('should create valid ES256 signature', async () => {
      const input: CreateJwtInput = {
        serviceProviderId: 'provider-123',
        localPatientId: 'patient-456',
        scope: 'fhir.read',
      };

      const jwt = await service.createJwt(input);

      // Should verify successfully with the public key
      await expect(jwtVerify(jwt, testPublicKey)).resolves.toBeDefined();
    });

    it('should include all input fields in JWT', async () => {
      const input: CreateJwtInput = {
        serviceProviderId: 'sp-abc',
        localPatientId: 'pat-xyz',
        scope: 'patient/*.read Observation.read',
        correlationId: 'req-12345',
      };

      const jwt = await service.createJwt(input);
      const { payload } = await jwtVerify(jwt, testPublicKey);

      expect(payload.sub).toBe(input.serviceProviderId);
      expect(payload.patient).toBe(input.localPatientId);
      expect(payload.scope).toBe(input.scope);
      expect(payload.correlation_id).toBe(input.correlationId);
    });
  });

  describe('JWT structure', () => {
    it('should create JWT with correct header', async () => {
      const input: CreateJwtInput = {
        serviceProviderId: 'provider-123',
        localPatientId: 'patient-456',
        scope: 'fhir.read',
      };

      const jwt = await service.createJwt(input);
      const [headerB64] = jwt.split('.');
      const header = JSON.parse(
        Buffer.from(headerB64, 'base64url').toString(),
      );

      expect(header.alg).toBe('RS256');
      expect(header.typ).toBe('JWT');
    });
  });
});
