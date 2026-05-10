/**
 * Safe PCM token acquisition check script
 * Tests PCM token acquisition without printing sensitive data
 */
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from '../app.module';
import { PcmTokenService } from '../pcm/pcm-token.service';

async function checkPcmToken() {
  console.log('PCM Token Acquisition Check');
  console.log('============================\n');

  try {
    // Create NestJS application context
    const app = await NestFactory.createApplicationContext(AppModule, {
      logger: ['error', 'warn'], // Suppress debug logs for clean output
    });

    // Get PCM token service
    const pcmTokenService = app.get(PcmTokenService);

    console.log('Acquiring token from PCM...\n');

    // Acquire token
    const result = await pcmTokenService.acquireToken();

    // Print safe output only (never print token value by default)
    console.log('✓ SUCCESS');
    console.log('─────────────────────────────');
    console.log(`Token Type:      ${result.token_type}`);
    console.log(`Expires In:      ${result.expires_in} seconds`);
    console.log(`Token Length:    ${result.access_token.length} characters`);
    console.log(`From Cache:      ${result.from_cache ? 'Yes' : 'No'}`);
    console.log('─────────────────────────────\n');

    // Optional: print full token for local debugging only
    if (process.env.PRINT_PCM_ACCESS_TOKEN === 'true') {
      console.log('⚠️  WARNING: Printing PCM access token for local debugging only.');
      console.log('⚠️  Do not share or commit this output.\n');
      console.log('Access Token:');
      console.log(result.access_token);
      console.log();
    }

    // Test cache if enabled
    if (!result.from_cache) {
      console.log('Testing token cache...\n');
      const cachedResult = await pcmTokenService.acquireToken();
      console.log(`Cache Status:    ${cachedResult.from_cache ? 'Working (token reused)' : 'Disabled or expired'}`);
      console.log();
    }

    await app.close();
    process.exit(0);
  } catch (error) {
    console.error('\n✗ FAILURE');
    console.error('─────────────────────────────');
    console.error(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    console.error('─────────────────────────────\n');

    console.error('Troubleshooting:');
    console.error('1. Check that all required environment variables are set');
    console.error('2. Verify certificate files exist and are readable');
    console.error('3. Ensure PCM endpoint is accessible');
    console.error('4. Check PCM client registration');
    console.error('5. Run: curl http://localhost:3009/ready\n');

    process.exit(1);
  }
}

void checkPcmToken();
