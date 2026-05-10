import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { ResponseVerificationService } from './response-verification.service';
import { SecurityError } from '../common';
import { FhirBundle, FhirResource } from './types/fhir-types';

describe('ResponseVerificationService', () => {
  let service: ResponseVerificationService;
  let configService: ConfigService;

  const mockForbiddenLabel = {
    system: 'http://fhir.health.gov.il/cs/il-core-main-security-label',
    code: 'V',
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ResponseVerificationService,
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn((key: string, defaultValue?: any) => {
              if (key === 'responseVerification.enabled') {
                return true;
              }
              if (key === 'responseVerification.forbiddenLabels') {
                return [mockForbiddenLabel];
              }
              return defaultValue;
            }),
          },
        },
      ],
    }).compile();

    service = module.get<ResponseVerificationService>(
      ResponseVerificationService,
    );
    configService = module.get<ConfigService>(ConfigService);
  });

  describe('Single Resource', () => {
    it('should pass clean resource without meta', () => {
      const resource: FhirResource = {
        resourceType: 'Patient',
        id: '123',
      };

      const result = service.verify(resource);
      expect(result.passed).toBe(true);
    });

    it('should pass clean resource with empty security', () => {
      const resource: FhirResource = {
        resourceType: 'Patient',
        id: '123',
        meta: {
          security: [],
        },
      };

      const result = service.verify(resource);
      expect(result.passed).toBe(true);
    });

    it('should pass resource with allowed security label', () => {
      const resource: FhirResource = {
        resourceType: 'Patient',
        id: '123',
        meta: {
          security: [
            {
              system: 'http://terminology.hl7.org/CodeSystem/v3-Confidentiality',
              code: 'N',
            },
          ],
        },
      };

      const result = service.verify(resource);
      expect(result.passed).toBe(true);
    });

    it('should fail resource with V security label', () => {
      const resource: FhirResource = {
        resourceType: 'Observation',
        id: '456',
        meta: {
          security: [
            {
              system: 'http://fhir.health.gov.il/cs/il-core-main-security-label',
              code: 'V',
            },
          ],
        },
      };

      const result = service.verify(resource);
      expect(result.passed).toBe(false);
      expect(result.forbiddenLabelFound).toEqual(mockForbiddenLabel);
      expect(result.resourceType).toBe('Observation');
    });

    it('should fail resource with V label among other labels', () => {
      const resource: FhirResource = {
        resourceType: 'Condition',
        id: '789',
        meta: {
          security: [
            {
              system: 'http://terminology.hl7.org/CodeSystem/v3-Confidentiality',
              code: 'N',
            },
            {
              system: 'http://fhir.health.gov.il/cs/il-core-main-security-label',
              code: 'V',
            },
          ],
        },
      };

      const result = service.verify(resource);
      expect(result.passed).toBe(false);
    });

    it('should not fail on different system with V code', () => {
      const resource: FhirResource = {
        resourceType: 'Patient',
        id: '123',
        meta: {
          security: [
            {
              system: 'http://different-system.example.com',
              code: 'V',
            },
          ],
        },
      };

      const result = service.verify(resource);
      expect(result.passed).toBe(true);
    });

    it('should not fail on same system with different code', () => {
      const resource: FhirResource = {
        resourceType: 'Patient',
        id: '123',
        meta: {
          security: [
            {
              system: 'http://fhir.health.gov.il/cs/il-core-main-security-label',
              code: 'R', // Restricted but not V
            },
          ],
        },
      };

      const result = service.verify(resource);
      expect(result.passed).toBe(true);
    });
  });

  describe('Bundle', () => {
    it('should pass clean bundle with no entries', () => {
      const bundle: FhirBundle = {
        resourceType: 'Bundle',
        type: 'searchset',
        entry: [],
      };

      const result = service.verify(bundle);
      expect(result.passed).toBe(true);
    });

    it('should pass bundle with clean resources', () => {
      const bundle: FhirBundle = {
        resourceType: 'Bundle',
        type: 'searchset',
        entry: [
          {
            resource: {
              resourceType: 'Patient',
              id: '1',
            },
          },
          {
            resource: {
              resourceType: 'Observation',
              id: '2',
              meta: {
                security: [
                  {
                    system:
                      'http://terminology.hl7.org/CodeSystem/v3-Confidentiality',
                    code: 'N',
                  },
                ],
              },
            },
          },
        ],
      };

      const result = service.verify(bundle);
      expect(result.passed).toBe(true);
    });

    it('should fail bundle with V-labeled resource in first entry', () => {
      const bundle: FhirBundle = {
        resourceType: 'Bundle',
        type: 'searchset',
        entry: [
          {
            resource: {
              resourceType: 'Observation',
              id: '1',
              meta: {
                security: [
                  {
                    system:
                      'http://fhir.health.gov.il/cs/il-core-main-security-label',
                    code: 'V',
                  },
                ],
              },
            },
          },
          {
            resource: {
              resourceType: 'Patient',
              id: '2',
            },
          },
        ],
      };

      const result = service.verify(bundle);
      expect(result.passed).toBe(false);
      expect(result.entryIndex).toBe(0);
      expect(result.resourceType).toBe('Observation');
    });

    it('should fail bundle with V-labeled resource in middle entry', () => {
      const bundle: FhirBundle = {
        resourceType: 'Bundle',
        type: 'searchset',
        entry: [
          {
            resource: {
              resourceType: 'Patient',
              id: '1',
            },
          },
          {
            resource: {
              resourceType: 'Condition',
              id: '2',
              meta: {
                security: [
                  {
                    system:
                      'http://fhir.health.gov.il/cs/il-core-main-security-label',
                    code: 'V',
                  },
                ],
              },
            },
          },
          {
            resource: {
              resourceType: 'Observation',
              id: '3',
            },
          },
        ],
      };

      const result = service.verify(bundle);
      expect(result.passed).toBe(false);
      expect(result.entryIndex).toBe(1);
      expect(result.resourceType).toBe('Condition');
    });
  });

  describe('Non-FHIR Responses', () => {
    it('should pass null response', () => {
      const result = service.verify(null);
      expect(result.passed).toBe(true);
    });

    it('should pass undefined response', () => {
      const result = service.verify(undefined);
      expect(result.passed).toBe(true);
    });

    it('should pass non-object response', () => {
      const result = service.verify('plain string');
      expect(result.passed).toBe(true);
    });

    it('should pass non-FHIR object', () => {
      const result = service.verify({ foo: 'bar' });
      expect(result.passed).toBe(true);
    });
  });

  describe('Disabled Verification', () => {
    let disabledService: ResponseVerificationService;

    beforeEach(async () => {
      const module: TestingModule = await Test.createTestingModule({
        providers: [
          ResponseVerificationService,
          {
            provide: ConfigService,
            useValue: {
              get: jest.fn((key: string, defaultValue?: any) => {
                if (key === 'responseVerification.enabled') {
                  return false; // Disabled
                }
                if (key === 'responseVerification.forbiddenLabels') {
                  return [mockForbiddenLabel];
                }
                return defaultValue;
              }),
            },
          },
        ],
      }).compile();

      disabledService = module.get<ResponseVerificationService>(
        ResponseVerificationService,
      );
    });

    it('should pass even with V label when disabled', () => {
      const resource: FhirResource = {
        resourceType: 'Observation',
        id: '123',
        meta: {
          security: [
            {
              system: 'http://fhir.health.gov.il/cs/il-core-main-security-label',
              code: 'V',
            },
          ],
        },
      };

      const result = disabledService.verify(resource);
      expect(result.passed).toBe(true);
    });
  });

  describe('verifyOrThrow', () => {
    it('should not throw for clean resource', () => {
      const resource: FhirResource = {
        resourceType: 'Patient',
        id: '123',
      };

      expect(() => service.verifyOrThrow(resource)).not.toThrow();
    });

    it('should throw SecurityError for V-labeled resource', () => {
      const resource: FhirResource = {
        resourceType: 'Observation',
        id: '456',
        meta: {
          security: [
            {
              system: 'http://fhir.health.gov.il/cs/il-core-main-security-label',
              code: 'V',
            },
          ],
        },
      };

      expect(() => service.verifyOrThrow(resource)).toThrow(SecurityError);
    });

    it('should throw SecurityError with internal details', () => {
      const resource: FhirResource = {
        resourceType: 'Observation',
        id: '456',
        meta: {
          security: [
            {
              system: 'http://fhir.health.gov.il/cs/il-core-main-security-label',
              code: 'V',
            },
          ],
        },
      };

      try {
        service.verifyOrThrow(resource);
        fail('Should have thrown SecurityError');
      } catch (error) {
        expect(error).toBeInstanceOf(SecurityError);
        if (error instanceof SecurityError) {
          expect(error.message).toContain('Forbidden security label detected');
          expect(error.message).toContain('Observation');
        }
      }
    });
  });
});
