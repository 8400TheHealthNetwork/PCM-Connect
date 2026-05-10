#!/usr/bin/env bash
# Generate the ES256 (P-256) private key used to sign internal JWTs the adapter
# forwards to the FHIR backend. This is DS_ADAPTER_JWT_SIGNING_KEY.
#
# Usage:
#   scripts/generate_jwt_signing_key.sh                       # → certs/jwt-signing.key
#   scripts/generate_jwt_signing_key.sh path/to/key.pem       # custom path
#   scripts/generate_jwt_signing_key.sh -f certs/jwt-signing.key   # overwrite if exists

set -euo pipefail

force=0
out=""
for arg in "$@"; do
  case "$arg" in
    -f|--force) force=1 ;;
    -h|--help)
      sed -n '2,11p' "$0"
      exit 0
      ;;
    *) out="$arg" ;;
  esac
done
out="${out:-certs/jwt-signing.key}"

if [[ -e "$out" && "$force" -eq 0 ]]; then
  echo "refusing to overwrite existing $out (pass -f to force)" >&2
  exit 1
fi

mkdir -p "$(dirname "$out")"
openssl ecparam -name prime256v1 -genkey -noout -out "$out"
chmod 600 "$out"

echo "wrote $out (ES256 / P-256)"
openssl pkey -in "$out" -text -noout | grep -E "Private-Key|ASN1 OID"
