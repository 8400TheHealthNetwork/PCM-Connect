import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { FhirUrlBuilderService } from './fhir-url-builder.service';

describe('FhirUrlBuilderService', () => {
  let service: FhirUrlBuilderService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        FhirUrlBuilderService,
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn((key: string, defaultValue?: any) => {
              const config: Record<string, any> = {
                'fhir.baseUrl': 'http://mock-fhir.local',
                'fhir.patientReferenceFormat': 'bare',
                'fhir.patientIdentifierSystem':
                  'http://fhir.health.gov.il/identifier/il-national-id',
                'responseVerification.forbiddenLabels.0.system':
                  'http://fhir.health.gov.il/cs/il-core-main-security-label',
                'responseVerification.forbiddenLabels.0.code': 'V',
              };
              return config[key] !== undefined ? config[key] : defaultValue;
            }),
          },
        },
      ],
    }).compile();

    service = module.get<FhirUrlBuilderService>(FhirUrlBuilderService);
  });

  describe('buildUrl', () => {
    it('should build URL without duplicating query parameters', () => {
      const path = '/Observation';
      const queryParams = new URLSearchParams('code=test');
      const localPatientId = 'mock-patient-0018';

      const url = service.buildUrl(path, queryParams, localPatientId);

      // Parse the URL to check params
      const parsedUrl = new URL(url);

      // Check that code appears only once
      expect(parsedUrl.searchParams.getAll('code')).toEqual(['test']);

      // Check that patient is injected once
      expect(parsedUrl.searchParams.getAll('patient')).toEqual([
        'mock-patient-0018',
      ]);

      // Check that _security:not is injected once
      expect(parsedUrl.searchParams.getAll('_security:not')).toEqual([
        'http://fhir.health.gov.il/cs/il-core-main-security-label|V',
      ]);
    });

    it('should inject patient parameter when not present', () => {
      const path = '/Observation';
      const queryParams = new URLSearchParams('code=vital-signs');
      const localPatientId = 'patient-123';

      const url = service.buildUrl(path, queryParams, localPatientId);
      const parsedUrl = new URL(url);

      expect(parsedUrl.searchParams.get('patient')).toBe('patient-123');
      expect(parsedUrl.searchParams.get('code')).toBe('vital-signs');
    });

    it('should not override existing patient parameter', () => {
      const path = '/Observation';
      const queryParams = new URLSearchParams('patient=existing-123');
      const localPatientId = 'patient-456';

      const url = service.buildUrl(path, queryParams, localPatientId);
      const parsedUrl = new URL(url);

      // Should keep the existing patient parameter
      expect(parsedUrl.searchParams.get('patient')).toBe('existing-123');
    });

    it('should inject _security:not parameter', () => {
      const path = '/Observation';
      const queryParams = new URLSearchParams();
      const localPatientId = 'patient-123';

      const url = service.buildUrl(path, queryParams, localPatientId);
      const parsedUrl = new URL(url);

      expect(parsedUrl.searchParams.get('_security:not')).toBe(
        'http://fhir.health.gov.il/cs/il-core-main-security-label|V',
      );
    });

    it('should preserve multiple query parameters', () => {
      const path = '/Observation';
      const queryParams = new URLSearchParams();
      queryParams.append('category', 'vital-signs');
      queryParams.append('date', 'ge2024-01-01');
      queryParams.append('code', 'test1');
      queryParams.append('code', 'test2');
      const localPatientId = 'patient-123';

      const url = service.buildUrl(path, queryParams, localPatientId);
      const parsedUrl = new URL(url);

      expect(parsedUrl.searchParams.get('category')).toBe('vital-signs');
      expect(parsedUrl.searchParams.get('date')).toBe('ge2024-01-01');
      expect(parsedUrl.searchParams.getAll('code')).toEqual(['test1', 'test2']);
    });

    it('should handle path with trailing slash', () => {
      const path = '/Observation/';
      const queryParams = new URLSearchParams();
      const localPatientId = 'patient-123';

      const url = service.buildUrl(path, queryParams, localPatientId);

      expect(url).toContain('/Observation/');
    });

    it('should use full patient reference format when configured', async () => {
      // Create a new service instance with full format
      const module = await Test.createTestingModule({
        providers: [
          FhirUrlBuilderService,
          {
            provide: ConfigService,
            useValue: {
              get: jest.fn((key: string, defaultValue?: any) => {
                const config: Record<string, any> = {
                  'fhir.baseUrl': 'http://mock-fhir.local',
                  'fhir.patientReferenceFormat': 'full',
                  'fhir.patientIdentifierSystem':
                    'http://fhir.health.gov.il/identifier/il-national-id',
                  'responseVerification.forbiddenLabels.0.system':
                    'http://fhir.health.gov.il/cs/il-core-main-security-label',
                  'responseVerification.forbiddenLabels.0.code': 'V',
                };
                return config[key] !== undefined ? config[key] : defaultValue;
              }),
            },
          },
        ],
      }).compile();

      const fullFormatService = module.get<FhirUrlBuilderService>(
        FhirUrlBuilderService,
      );

      const path = '/Observation';
      const queryParams = new URLSearchParams();
      const localPatientId = 'patient-123';

      const url = fullFormatService.buildUrl(path, queryParams, localPatientId);
      const parsedUrl = new URL(url);

      expect(parsedUrl.searchParams.get('patient')).toBe('Patient/patient-123');
    });
  });
});
