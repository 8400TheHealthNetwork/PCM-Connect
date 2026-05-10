/**
 * Safe PCM introspection check script
 * Tests PCM introspection of opaque Service Provider token without printing sensitive data
 */
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from '../app.module';
import { PcmIntrospectionService } from '../pcm/pcm-introspection.service';

async function checkPcmIntrospection() {
  console.log('PCM Introspection Check');
  console.log('=======================\n');

  // Get opaque token from environment
  const opaqueToken = process.env.PCM_OPAQUE_TOKEN;

  if (!opaqueToken || opaqueToken.trim() === '') {
    console.error('✗ FAILURE');
    console.error('─────────────────────────────');
    console.error('PCM_OPAQUE_TOKEN is required');
    console.error('─────────────────────────────\n');
    console.error('Usage:');
    console.error('  PCM_OPAQUE_TOKEN=<token> npm run pcm:introspect:check\n');
    console.error('Note:');
    console.error('  The opaque token should be a Service Provider token obtained from PCM,');
    console.error('  NOT the adapter client token from pcm:token:check.\n');
    process.exit(1);
  }

  console.log('Opaque Token:    Provided (not displayed for security)');
  console.log('Token Length:    ' + opaqueToken.length + ' characters\n');

  try {
    // Create NestJS application context
    const app = await NestFactory.createApplicationContext(AppModule, {
      logger: ['error', 'warn'], // Suppress debug logs for clean output
    });

    // Get PCM introspection service
    const pcmIntrospectionService = app.get(PcmIntrospectionService);

    console.log('Introspecting token with PCM...\n');

    // Introspect token
    const result = await pcmIntrospectionService.introspect(opaqueToken);

    // Print safe output only (never print token values)
    console.log('✓ SUCCESS');
    console.log('─────────────────────────────');
    console.log(`Active:          ${result.active}`);

    if (result.client_id) {
      console.log(`Client ID:       ${result.client_id}`);
    }

    if (result.patient) {
      // Mask patient ID for privacy (show last 4 chars only)
      const maskedPatient =
        result.patient.length > 4
          ? '****' + result.patient.slice(-4)
          : '****';
      console.log(`Patient:         ${maskedPatient}`);
    }

    if (result.scope) {
      // Show scope summary, not full content (may be sensitive)
      const scopeCount = result.scope.split(' ').filter((s) => s).length;
      console.log(`Scope Count:     ${scopeCount} permissions`);
    }

    if (result.consent_id) {
      console.log(`Consent ID:      ${result.consent_id}`);
    }

    if (result.baskets && Array.isArray(result.baskets)) {
      console.log(`Baskets:         ${result.baskets.length} basket(s)`);
    }

    if (result.access_type) {
      console.log(`Access Type:     ${result.access_type}`);
    }

    if (result.sp_organization_id) {
      console.log(`SP Org ID:       ${result.sp_organization_id}`);
    }

    if (result.intent) {
      console.log(`Intent:          ${result.intent}`);
    }

    if (result.exp) {
      const now = Math.floor(Date.now() / 1000);
      const expiresIn = result.exp - now;
      console.log(`Expires In:      ${expiresIn} seconds`);
    }

    if (result.aud) {
      console.log(`Audience:        ${result.aud}`);
    }

    if (result.iss) {
      console.log(`Issuer:          ${result.iss}`);
    }

    // List all field names present (for debugging structure)
    const fieldNames = Object.keys(result).filter(
      (k) => !['active'].includes(k),
    );
    console.log(`Fields Present:  ${fieldNames.join(', ')}`);

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
    console.error('1. Ensure PCM_OPAQUE_TOKEN contains a valid Service Provider token');
    console.error('2. Check that PCM client token acquisition works (npm run pcm:token:check)');
    console.error('3. Verify PCM endpoint is accessible');
    console.error('4. Check that the opaque token has not expired\n');

    process.exit(1);
  }
}

void checkPcmIntrospection();
