#!/usr/bin/env python3
"""Export the OpenAPI 3.1 specification from the Orbital Inspect FastAPI app.

Usage:
    cd backend && python -m scripts.export_openapi [--output openapi.json]

Generates a machine-readable OpenAPI spec suitable for SDK code generation,
API documentation portals, and integration testing.
"""

import argparse
import json
import os
import sys

# Ensure backend/ is on the path when run as a module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GEMINI_API_KEY", "unused-for-export")
os.environ.setdefault("DEMO_MODE", "true")


def export_openapi(output_path: str = "openapi.json") -> None:
    from main import app

    schema = app.openapi()

    # Enrich with server URLs for common environments
    schema["servers"] = [
        {"url": "http://localhost:8000", "description": "Local development"},
        {"url": "https://api.orbital-inspect.example.com", "description": "Production"},
    ]

    # Add security scheme definitions
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token obtained from the auth endpoint.",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Organization-scoped API key (prefix: oi-).",
        },
    }

    # Apply global security (both schemes accepted)
    schema["security"] = [
        {"BearerAuth": []},
        {"ApiKeyAuth": []},
    ]

    # Add contact and license info
    schema["info"]["contact"] = {
        "name": "Orbital Inspect Engineering",
        "url": "https://orbital-inspect.example.com",
    }
    schema["info"]["license"] = {
        "name": "Business Source License 1.1",
        "url": "https://mariadb.com/bsl11/",
    }

    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2, default=str)

    # Summary stats
    paths = schema.get("paths", {})
    endpoint_count = sum(len(methods) for methods in paths.values())
    print(f"Exported {endpoint_count} endpoints across {len(paths)} paths to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export OpenAPI spec")
    parser.add_argument(
        "--output", "-o",
        default="openapi.json",
        help="Output file path (default: openapi.json)",
    )
    args = parser.parse_args()
    export_openapi(args.output)
