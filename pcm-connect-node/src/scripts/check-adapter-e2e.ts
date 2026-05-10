/**
 * End-to-End Adapter Check Script
 * Tests the complete /fhir/* proxy flow with mock modes
 * Safe output only - no tokens or sensitive data printed
 */
import 'reflect-metadata';

async function checkAdapterE2e() {
  console.log('PCM/FHIR Adapter E2E Check');
  console.log('==========================\n');

  const baseUrl = process.env.ADAPTER_BASE_URL || 'http://localhost:3009';
  const testEndpoint = '/fhir/Observation?category=vital-signs';
  const fullUrl = `${baseUrl}${testEndpoint}`;

  console.log(`Target: ${fullUrl}`);
  console.log(`Authorization: Bearer dummy-local-token (masked)\n`);

  try {
    const response = await fetch(fullUrl, {
      method: 'GET',
      headers: {
        Authorization: 'Bearer dummy-local-token',
        Accept: 'application/fhir+json',
      },
    });

    // Extract correlation ID from response headers if present
    const correlationId = response.headers.get('x-correlation-id') || 'not-set';

    // Parse response
    const body = await response.json();

    // Print safe summary
    console.log('✓ SUCCESS');
    console.log('─────────────────────────────');
    console.log(`HTTP Status:       ${response.status} ${response.statusText}`);
    console.log(`Resource Type:     ${body.resourceType || 'unknown'}`);

    if (body.resourceType === 'Bundle') {
      console.log(`Bundle Type:       ${body.type || 'unknown'}`);
      console.log(`Total Entries:     ${body.total ?? body.entry?.length ?? 0}`);

      if (body.entry && body.entry.length > 0) {
        const resourceTypes = body.entry
          .map((e: any) => e.resource?.resourceType)
          .filter((t: any) => t);
        const uniqueTypes = [...new Set(resourceTypes)];
        console.log(`Entry Types:       ${uniqueTypes.join(', ')}`);
      }
    } else if (body.resourceType === 'OperationOutcome') {
      console.log(`Issue Severity:    ${body.issue?.[0]?.severity || 'unknown'}`);
      console.log(`Issue Code:        ${body.issue?.[0]?.code || 'unknown'}`);
    }

    console.log(`Correlation ID:    ${correlationId}`);
    console.log('─────────────────────────────\n');

    if (response.status !== 200) {
      console.error('✗ Non-200 status received');
      process.exit(1);
    }

    if (body.resourceType !== 'Bundle') {
      console.error(`✗ Expected Bundle, got ${body.resourceType}`);
      process.exit(1);
    }

    console.log('All checks passed!\n');
    process.exit(0);
  } catch (error) {
    console.error('\n✗ FAILURE');
    console.error('─────────────────────────────');
    console.error(
      `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
    );
    console.error('─────────────────────────────\n');

    console.error('Troubleshooting:');
    console.error('1. Ensure server is running: npm start');
    console.error('2. Check mock modes are enabled:');
    console.error('   PCM_INTROSPECTION_MODE=mock');
    console.error('   FHIR_FORWARDING_MODE=mock');
    console.error('   ID_REPLACEMENT_MODE=mock');
    console.error('3. Verify configuration is valid\n');

    process.exit(1);
  }
}

void checkAdapterE2e();
