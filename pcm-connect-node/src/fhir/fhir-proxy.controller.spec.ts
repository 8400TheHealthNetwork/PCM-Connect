import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { FhirProxyController } from './fhir-proxy.controller';
import { PcmIntrospectionService } from '../pcm/pcm-introspection.service';
import { IdReplacementService } from '../identity/id-replacement.service';
import { InternalJwtService } from '../jwt/internal-jwt.service';
import { FhirUrlBuilderService } from './fhir-url-builder.service';
import { FhirForwardService } from './fhir-forward.service';
import { ResponseVerificationService } from '../verification/response-verification.service';
import { AuditService } from '../audit/audit.service';
import { FastifyRequest, FastifyReply } from 'fastify';

describe('FhirProxyController', () => {
  let controller: FhirProxyController;
  let mockPcmService: jest.Mocked<PcmIntrospectionService>;
  let mockIdService: jest.Mocked<IdReplacementService>;
  let mockJwtService: jest.Mocked<InternalJwtService>;
  let mockUrlBuilder: jest.Mocked<FhirUrlBuilderService>;
  let mockForwardService: jest.Mocked<FhirForwardService>;
  let mockVerificationService: jest.Mocked<ResponseVerificationService>;
  let mockAuditService: jest.Mocked<AuditService>;

  beforeEach(async () => {
    // Create mocks
    mockPcmService = {
      introspect: jest.fn(),
    } as any;

    mockIdService = {
      resolve: jest.fn(),
    } as any;

    mockJwtService = {
      createJwt: jest.fn(),
    } as any;

    mockUrlBuilder = {
      buildUrl: jest.fn(),
    } as any;

    mockForwardService = {
      forward: jest.fn(),
    } as any;

    mockVerificationService = {
      verify: jest.fn(),
    } as any;

    mockAuditService = {
      audit: jest.fn(),
    } as any;

    const module: TestingModule = await Test.createTestingModule({
      controllers: [FhirProxyController],
      providers: [
        { provide: PcmIntrospectionService, useValue: mockPcmService },
        { provide: IdReplacementService, useValue: mockIdService },
        { provide: InternalJwtService, useValue: mockJwtService },
        { provide: FhirUrlBuilderService, useValue: mockUrlBuilder },
        { provide: FhirForwardService, useValue: mockForwardService },
        {
          provide: ResponseVerificationService,
          useValue: mockVerificationService,
        },
        { provide: AuditService, useValue: mockAuditService },
      ],
    }).compile();

    controller = module.get<FhirProxyController>(FhirProxyController);
  });

  describe('proxyFhirRequest', () => {
    let mockRequest: Partial<FastifyRequest>;
    let mockReply: Partial<FastifyReply>;

    beforeEach(() => {
      mockRequest = {
        headers: {},
        url: '/fhir/Observation?code=test',
        method: 'GET',
      } as any;

      mockReply = {
        status: jest.fn().mockReturnThis(),
        send: jest.fn().mockReturnThis(),
      } as any;
    });

    it('should return 401 when Authorization header is missing', async () => {
      await controller.proxyFhirRequest(
        mockRequest as FastifyRequest,
        mockReply as FastifyReply,
      );

      expect(mockReply.status).toHaveBeenCalledWith(401);
      expect(mockReply.send).toHaveBeenCalledWith(
        expect.objectContaining({
          resourceType: 'OperationOutcome',
          issue: expect.arrayContaining([
            expect.objectContaining({
              severity: 'error',
              code: 'security',
            }),
          ]),
        }),
      );
      expect(mockAuditService.audit).toHaveBeenCalledWith(
        expect.objectContaining({
          outcome: 'failure',
          statusCode: 401,
          errorCode: 'missing_authorization',
        }),
      );
    });

    it('should return 401 when Authorization header does not start with Bearer', async () => {
      mockRequest.headers!.authorization = 'Basic abc123';

      await controller.proxyFhirRequest(
        mockRequest as FastifyRequest,
        mockReply as FastifyReply,
      );

      expect(mockReply.status).toHaveBeenCalledWith(401);
      expect(mockAuditService.audit).toHaveBeenCalledWith(
        expect.objectContaining({
          outcome: 'failure',
          errorCode: 'missing_authorization',
        }),
      );
    });

    it('should return 401 when token is inactive', async () => {
      mockRequest.headers!.authorization = 'Bearer test-token';
      mockPcmService.introspect.mockResolvedValue({
        active: false,
      } as any);

      await controller.proxyFhirRequest(
        mockRequest as FastifyRequest,
        mockReply as FastifyReply,
      );

      expect(mockPcmService.introspect).toHaveBeenCalledWith('test-token');
      expect(mockReply.status).toHaveBeenCalledWith(401);
      expect(mockAuditService.audit).toHaveBeenCalledWith(
        expect.objectContaining({
          outcome: 'failure',
          errorCode: 'token_inactive',
        }),
      );
    });

    it('should return 400 when introspection missing patient field', async () => {
      mockRequest.headers!.authorization = 'Bearer test-token';
      mockPcmService.introspect.mockResolvedValue({
        active: true,
        patient: undefined,
      } as any);

      await controller.proxyFhirRequest(
        mockRequest as FastifyRequest,
        mockReply as FastifyReply,
      );

      expect(mockReply.status).toHaveBeenCalledWith(400);
      expect(mockAuditService.audit).toHaveBeenCalledWith(
        expect.objectContaining({
          outcome: 'failure',
          errorCode: 'missing_patient',
        }),
      );
    });

    it('should successfully proxy request and return FHIR Bundle', async () => {
      mockRequest.headers!.authorization = 'Bearer test-token';

      // Mock successful flow
      mockPcmService.introspect.mockResolvedValue({
        active: true,
        patient: '000000018',
        client_id: 'test-client',
        scope: 'patient/Observation.rs',
      } as any);

      mockIdService.resolve.mockResolvedValue({
        localPatientId: 'mock-patient-0018',
        resourceReference: 'Patient/mock-patient-0018',
      });

      mockJwtService.createJwt.mockResolvedValue('mock-jwt-token');

      mockUrlBuilder.buildUrl.mockReturnValue(
        'http://mock-fhir.local/Observation?code=test&patient=mock-patient-0018',
      );

      const mockBundle = {
        resourceType: 'Bundle',
        type: 'searchset',
        total: 1,
        entry: [],
      };
      mockForwardService.forward.mockResolvedValue(mockBundle);

      mockVerificationService.verify.mockReturnValue({
        passed: true,
      });

      await controller.proxyFhirRequest(
        mockRequest as FastifyRequest,
        mockReply as FastifyReply,
      );

      expect(mockPcmService.introspect).toHaveBeenCalledWith('test-token');
      expect(mockIdService.resolve).toHaveBeenCalledWith(
        expect.objectContaining({
          identifierValue: '000000018',
        }),
      );
      expect(mockJwtService.createJwt).toHaveBeenCalled();
      expect(mockUrlBuilder.buildUrl).toHaveBeenCalled();
      expect(mockForwardService.forward).toHaveBeenCalledWith(
        expect.any(String),
        'mock-jwt-token',
        expect.any(String),
      );
      expect(mockVerificationService.verify).toHaveBeenCalledWith(mockBundle);
      expect(mockReply.status).toHaveBeenCalledWith(200);
      expect(mockReply.send).toHaveBeenCalledWith(mockBundle);
      expect(mockAuditService.audit).toHaveBeenCalledWith(
        expect.objectContaining({
          outcome: 'success',
          statusCode: 200,
        }),
      );
    });

    it('should return 403 when response verification fails', async () => {
      mockRequest.headers!.authorization = 'Bearer test-token';

      mockPcmService.introspect.mockResolvedValue({
        active: true,
        patient: '000000018',
        client_id: 'test-client',
      } as any);

      mockIdService.resolve.mockResolvedValue({
        localPatientId: 'mock-patient-0018',
        resourceReference: 'Patient/mock-patient-0018',
      });

      mockJwtService.createJwt.mockResolvedValue('mock-jwt-token');
      mockUrlBuilder.buildUrl.mockReturnValue('http://mock-fhir.local/test');
      mockForwardService.forward.mockResolvedValue({ resourceType: 'Bundle' });

      // Verification fails
      mockVerificationService.verify.mockReturnValue({
        passed: false,
        forbiddenLabelFound: {
          system: 'http://test',
          code: 'V',
        },
      });

      await controller.proxyFhirRequest(
        mockRequest as FastifyRequest,
        mockReply as FastifyReply,
      );

      expect(mockReply.status).toHaveBeenCalledWith(403);
      expect(mockAuditService.audit).toHaveBeenCalledWith(
        expect.objectContaining({
          outcome: 'failure',
          errorCode: 'response_verification_failed',
        }),
      );
    });

    it('should return 500 on internal error', async () => {
      mockRequest.headers!.authorization = 'Bearer test-token';
      mockPcmService.introspect.mockRejectedValue(
        new Error('Network error'),
      );

      await controller.proxyFhirRequest(
        mockRequest as FastifyRequest,
        mockReply as FastifyReply,
      );

      expect(mockReply.status).toHaveBeenCalledWith(500);
      expect(mockReply.send).toHaveBeenCalledWith(
        expect.objectContaining({
          resourceType: 'OperationOutcome',
          issue: expect.arrayContaining([
            expect.objectContaining({
              severity: 'error',
              code: 'exception',
            }),
          ]),
        }),
      );
      expect(mockAuditService.audit).toHaveBeenCalledWith(
        expect.objectContaining({
          outcome: 'failure',
          errorCode: 'internal_error',
        }),
      );
    });
  });
});
