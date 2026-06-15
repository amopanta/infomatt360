"""
Proyecto: InfoMatt360
Modulo: Runtime Package Schemas
Responsabilidad: Definir contratos estables del paquete compilado que consumira Runtime.
"""

from typing import Any
from pydantic import BaseModel, Field


class RuntimeFieldSchema(BaseModel):
    name: str
    label: str
    type: str
    required: bool = False
    page_id: str | None = None
    section_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class RuntimeSchema(BaseModel):
    template_id: str
    name: str
    fields: list[RuntimeFieldSchema]
    layout: dict[str, Any] = Field(default_factory=dict)


class RuntimeExpression(BaseModel):
    field: str
    expression_type: str
    expression: str
    dependencies: list[str]


class RuntimePerformanceProfile(BaseModel):
    fields: int
    repeats: int
    expressions: int
    dependency_edges: int
    complexity: str
    recommendations: list[str]


class RuntimePackageManifest(BaseModel):
    template_id: str
    name: str
    compiler_version: str = "1.0.0"
    package_version: str = "1.0.0"
    generated_files: list[str]


class RuntimePackage(BaseModel):
    manifest: RuntimePackageManifest
    schema_: RuntimeSchema = Field(alias="schema")
    dependency_graph: dict[str, list[str]]
    expression_map: dict[str, RuntimeExpression]
    pulldata_map: dict[str, Any] = Field(default_factory=dict)
    performance_profile: RuntimePerformanceProfile
    version: dict[str, str]
