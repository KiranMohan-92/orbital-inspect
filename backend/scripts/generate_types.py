"""
Generate TypeScript interfaces from Pydantic models.

Usage: python scripts/generate_types.py > ../frontend/src/generated-types.ts
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.satellite import (
    OrbitalRegime, SatelliteType, UnderwritingRecommendation,
    SatelliteTarget, ClassificationResult, SatelliteDamageItem,
    SatelliteDamagesAssessment, OrbitalStressor, OrbitalEnvironmentAnalysis,
    SatellitePrecedent, SatelliteFailureModeAnalysis,
    RiskMatrixDimension, RiskMatrix, ConsistencyCheck,
    InsuranceRiskReport, SatelliteConditionReport,
)
from models.events import AgentEvent


def python_type_to_ts(python_type: str, field_info: dict | bool) -> str:
    """Convert JSON Schema type to TypeScript type."""
    if not isinstance(field_info, dict):
        return "unknown"

    if "$ref" in field_info:
        ref_name = field_info["$ref"].split("/")[-1]
        return ref_name

    json_type = field_info.get("type", "any")

    if json_type == "string":
        if "enum" in field_info:
            return " | ".join(f'"{v}"' for v in field_info["enum"])
        return "string"
    elif json_type == "integer" or json_type == "number":
        return "number"
    elif json_type == "boolean":
        return "boolean"
    elif json_type == "array":
        items = field_info.get("items", {})
        item_type = python_type_to_ts("", items)
        return f"{item_type}[]"
    elif json_type == "object":
        if "additionalProperties" in field_info:
            val_type = python_type_to_ts("", field_info["additionalProperties"])
            return f"Record<string, {val_type}>"
        return "Record<string, unknown>"
    elif json_type == "null":
        return "null"

    # Handle anyOf (Optional types)
    if "anyOf" in field_info:
        types = []
        for option in field_info["anyOf"]:
            t = python_type_to_ts("", option)
            if t != "null":
                types.append(t)
            else:
                types.append("null")
        return " | ".join(types)

    return "unknown"


def schema_to_interface(name: str, schema: dict, defs: dict) -> str:
    """Convert a JSON Schema to a TypeScript interface."""
    lines = [f"export interface {name} {{"]

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    for prop_name, prop_info in properties.items():
        # Resolve $ref
        if "$ref" in prop_info:
            ref_path = prop_info["$ref"]
            ref_name = ref_path.split("/")[-1]
            if ref_name in defs:
                ref_schema = defs[ref_name]
                if "enum" in ref_schema:
                    ts_type = " | ".join(f'"{v}"' for v in ref_schema["enum"])
                else:
                    ts_type = ref_name
            else:
                ts_type = ref_name
        else:
            ts_type = python_type_to_ts(prop_name, prop_info)

        optional = "" if prop_name in required else "?"
        lines.append(f"  {prop_name}{optional}: {ts_type};")

    lines.append("}")
    return "\n".join(lines)


def generate_all() -> str:
    """Generate all TypeScript types from Pydantic models."""
    output_lines = [
        "/**",
        " * Auto-generated TypeScript types from Pydantic models.",
        " * DO NOT EDIT MANUALLY — run: python backend/scripts/generate_types.py",
        " * Generated from backend/models/satellite.py and backend/models/events.py",
        " */",
        "",
    ]

    # Generate enum/union types
    models_with_enums = [
        ("OrbitalRegime", OrbitalRegime),
        ("SatelliteType", SatelliteType),
        ("UnderwritingRecommendation", UnderwritingRecommendation),
    ]

    for name, enum_cls in models_with_enums:
        values = " | ".join(f'"{m.value}"' for m in enum_cls)
        output_lines.append(f"export type {name} = {values};")
        output_lines.append("")

    # Additional union types not in enums
    output_lines.append('export type DamageSeverity = "MINOR" | "MODERATE" | "SEVERE" | "CRITICAL";')
    output_lines.append('export type ProgressionRate = "SLOW" | "MODERATE" | "RAPID" | "SUDDEN";')
    output_lines.append('export type StressorSeverity = "LOW" | "MEDIUM" | "HIGH";')
    output_lines.append('export type AssetType = "satellite" | "servicer" | "station_module" | "solar_array" | "radiator" | "power_node" | "compute_platform" | "other";')
    output_lines.append('export type AgentName = "orbital_classification" | "satellite_vision" | "orbital_environment" | "failure_mode" | "insurance_risk";')
    output_lines.append('export type AgentStatusType = "queued" | "thinking" | "complete" | "error";')
    output_lines.append('export type AnalysisStatus = "idle" | "analyzing" | "completed" | "completed_partial" | "failed" | "rejected" | "error";')
    output_lines.append("")

    # Generate interfaces from Pydantic models
    interface_models = [
        SatelliteTarget,
        ClassificationResult,
        SatelliteDamageItem,
        SatelliteDamagesAssessment,
        OrbitalStressor,
        OrbitalEnvironmentAnalysis,
        SatellitePrecedent,
        SatelliteFailureModeAnalysis,
        RiskMatrixDimension,
        RiskMatrix,
        ConsistencyCheck,
        InsuranceRiskReport,
        SatelliteConditionReport,
        AgentEvent,
    ]

    for model in interface_models:
        schema = model.model_json_schema()
        defs = schema.get("$defs", {})
        interface = schema_to_interface(model.__name__, schema, defs)
        output_lines.append(interface)
        output_lines.append("")

    return "\n".join(output_lines)


if __name__ == "__main__":
    output = generate_all()

    # Write to frontend
    output_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "generated-types.ts"
    output_path.write_text(output, encoding="utf-8")
    print(f"Generated {output_path}")
