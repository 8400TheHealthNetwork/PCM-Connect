from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import json


EXPECTED_SYSTEM = "http://fhir.health.gov.il/identifier/il-national-id"
EXPECTED_VALUE = "000000018"


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/fhir+json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/fhir/r4/Patient":
            self._send_json(404, {"error": "not_found"})
            return

        query = parse_qs(parsed.query)
        identifier = query.get("identifier", [""])[0]
        expected = f"{EXPECTED_SYSTEM}|{EXPECTED_VALUE}"

        if identifier == expected:
            bundle = {
                "resourceType": "Bundle",
                "type": "searchset",
                "total": 1,
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "12345",
                            "identifier": [
                                {
                                    "system": EXPECTED_SYSTEM,
                                    "value": EXPECTED_VALUE,
                                }
                            ],
                        }
                    }
                ],
            }
            self._send_json(200, bundle)
            return

        bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 0,
            "entry": [],
        }
        self._send_json(200, bundle)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8765), Handler)
    print("Mock FHIR server running on http://127.0.0.1:8765")
    server.serve_forever()
