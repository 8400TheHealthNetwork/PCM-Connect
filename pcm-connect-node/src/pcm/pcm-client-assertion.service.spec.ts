import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { PcmClientAssertionService } from './pcm-client-assertion.service';
import { generateKeyPair, type KeyLike, jwtVerify } from 'jose';

describe('PcmClientAssertionService', () => {
  let service: PcmClientAssertionService;
  let testPrivateKey: KeyLike;
  let testPublicKey: KeyLike;

  beforeAll(async () => {
    // Generate test ES256 key pair
    const keyPair = await generateKeyPair('ES256');
    testPrivateKey = keyPair.privateKey;
    testPublicKey = keyPair.publicKey;
  });

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PcmClientAssertionService,
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn((key: string, defaultValue?: any) => {
              const config: Record<string, any> = {
                'pcm.clientId': 'https://connecthon-python.demo',
                'pcm.clientAssertion.audience':
                  'https://pcm-test.example.com:4501/token',
                'pcm.clientAssertion.privateKeyPath': '', // Will use mock key
                'pcm.clientAssertion.algorithm': 'ES256',
              };
              return config[key] !== undefined ? config[key] : defaultValue;
            }),
          },
        },
      ],
    }).compile();

    service = module.get<PcmClientAssertionService>(
      PcmClientAssertionService,
    );

    // Set mock private key to avoid file system access
    service.setMockPrivateKey(testPrivateKey);
  });

  describe('createClientAssertion', () => {
    it('should create a valid JWT', async () => {
      const jwt = await service.createClientAssertion();

      expect(jwt).toBeDefined();
      expect(typeof jwt).toBe('string');
      expect(jwt.split('.')).toHaveLength(3);
    });

    it('should include required claims', async () => {
      const jwt = await service.createClientAssertion();
      const { payload } = await jwtVerify(jwt, testPublicKey);

      expect(payload.iss).toBe('https://connecthon-python.demo');
      expect(payload.sub).toBe('https://connecthon-python.demo');
      expect(payload.aud).toBe('https://pcm-test.example.com:4501/token');
      expect(payload.iat).toBeDefined();
      expect(payload.exp).toBeDefined();
      expect(payload.jti).toBeDefined();
    });

    it('should set expiry to 60 seconds', async () => {
      const beforeCreate = Math.floor(Date.now() / 1000);
      const jwt = await service.createClientAssertion();
      const afterCreate = Math.floor(Date.now() / 1000);

      const { payload } = await jwtVerify(jwt, testPublicKey);

      const iat = payload.iat as number;
      const exp = payload.exp as number;

      expect(exp - iat).toBe(60);
      expect(iat).toBeGreaterThanOrEqual(beforeCreate);
      expect(iat).toBeLessThanOrEqual(afterCreate);
    });

    it('should use ES256 algorithm', async () => {
      const jwt = await service.createClientAssertion();
      const [headerB64] = jwt.split('.');
      const header = JSON.parse(Buffer.from(headerB64, 'base64url').toString());

      expect(header.alg).toBe('ES256');
      expect(header.typ).toBe('JWT');
    });

    it('should include unique jti for each assertion', async () => {
      const jwt1 = await service.createClientAssertion();
      const jwt2 = await service.createClientAssertion();

      const { payload: payload1 } = await jwtVerify(jwt1, testPublicKey);
      const { payload: payload2 } = await jwtVerify(jwt2, testPublicKey);

      expect(payload1.jti).toBeDefined();
      expect(payload2.jti).toBeDefined();
      expect(payload1.jti).not.toBe(payload2.jti);
    });

    it('should throw if private key not loaded', async () => {
      const moduleWithoutKey: TestingModule = await Test.createTestingModule({
        providers: [
          PcmClientAssertionService,
          {
            provide: ConfigService,
            useValue: {
              get: jest.fn((key: string, defaultValue?: any) => {
                if (key === 'pcm.clientAssertion.algorithm') {
                  return 'ES256';
                }
                return defaultValue || '';
              }),
            },
          },
        ],
      }).compile();

      const serviceWithoutKey = moduleWithoutKey.get<PcmClientAssertionService>(
        PcmClientAssertionService,
      );

      await expect(serviceWithoutKey.createClientAssertion()).rejects.toThrow(
        'Client assertion private key not loaded',
      );
    });
  });
});
