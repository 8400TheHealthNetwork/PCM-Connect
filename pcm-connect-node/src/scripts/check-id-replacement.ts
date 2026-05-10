/**
 * Safe ID Replacement check script
 * Tests ID resolution without printing full patient identifiers
 */
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from '../app.module';
import { IdReplacementService } from '../identity/id-replacement.service';

async function checkIdReplacement() {
  console.log('ID Replacement Check');
  console.log('====================\n');

  try {
    // Get test identifier from environment (default for demo)
    const testIdentifier = process.env.ID_REPLACEMENT_TEST_IDENTIFIER || '000000018';

    // Mask identifier for display
    const maskedIdentifier =
      testIdentifier.length > 4
        ? '****' + testIdentifier.slice(-4)
        : '****';

    console.log(`Test Identifier: ${maskedIdentifier} (masked for security)`);
    console.log();

    // Create NestJS application context
    const app = await NestFactory.createApplicationContext(AppModule, {
      logger: ['error', 'warn'], // Suppress debug logs
    });

    // Get ID Replacement service
    const idReplacementService = app.get(IdReplacementService);

    console.log('Resolving patient identifier...\n');

    // Resolve identifier
    const result = await idReplacementService.resolve({
      identifierSystem: 'http://fhir.health.gov.il/identifier/il-national-id',
      identifierValue: testIdentifier,
    });

    // Print safe output only (never print full patient ID)
    console.log('✓ SUCCESS');
    console.log('─────────────────────────────');
    console.log(`Local Patient ID:      ${result.localPatientId}`);
    console.log(`Resource Reference:    ${result.resourceReference}`);
    console.log('─────────────────────────────\n');

    await app.close();
    process.exit(0);
  } catch (error) {
    console.error('\n✗ FAILURE');
    console.error('─────────────────────────────');
    console.error(
      `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
    );
    console.error('─────────────────────────────\n');

    console.error('Troubleshooting:');
    console.error('1. Check ID_REPLACEMENT_MODE configuration');
    console.error('2. For HTTP mode, verify ID_REPLACEMENT_BASE_URL is accessible');
    console.error('3. For mock mode, this should always succeed\n');

    process.exit(1);
  }
}

void checkIdReplacement();
