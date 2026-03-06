"""Excel/CSV tool definitions for the AI agent (BL-267).

Provides the extract_data tool that the agent can call to extract
structured data from uploaded spreadsheets using a schema definition.
"""

from __future__ import annotations

from ..services.multimodal.document_store import DocumentStore
from ..services.multimodal.excel_processor import (
    extract_data_with_schema,
    extract_from_file,
)
from ..services.tool_registry import ToolContext, ToolDefinition


def extract_data(args: dict, ctx: ToolContext) -> dict:
    """Extract structured data from an uploaded spreadsheet using a schema.

    The schema maps spreadsheet columns to output fields with type coercion.
    """
    file_id = args.get("file_id", "")
    schema = args.get("schema", {})
    sheet_name = args.get("sheet_name")

    if not file_id:
        return {"error": "file_id is required"}

    fields = schema.get("fields", [])
    if not fields:
        return {
            "error": "schema.fields is required (list of {name, type?, source_column?})"
        }

    store = DocumentStore()
    info = store.get_upload_info(file_id, ctx.tenant_id)
    if not info:
        return {"error": "File not found: {}".format(file_id)}

    storage_path = info.get("storage_path", "")
    if not storage_path:
        return {"error": "File has no storage path"}

    result = extract_data_with_schema(storage_path, fields, sheet_name)

    if result.error:
        return {"error": result.error}

    return {
        "filename": info.get("filename", ""),
        "rows": result.rows,
        "row_count": len(result.rows),
        "unmapped_columns": result.unmapped_columns,
        "warnings": result.warnings[:20],  # Cap warnings
    }


def analyze_spreadsheet(args: dict, ctx: ToolContext) -> dict:
    """Analyze an uploaded spreadsheet and return markdown content.

    Returns sheet discovery info and markdown representation
    (full table for small sheets, summary for large ones).
    """
    file_id = args.get("file_id", "")
    query = args.get("query", "")
    sheet_name = args.get("sheet_name")

    if not file_id:
        return {"error": "file_id is required"}

    store = DocumentStore()
    info = store.get_upload_info(file_id, ctx.tenant_id)
    if not info:
        return {"error": "File not found: {}".format(file_id)}

    storage_path = info.get("storage_path", "")
    if not storage_path:
        return {"error": "File has no storage path"}

    result = extract_from_file(storage_path, sheet_name)

    if result.errors:
        return {"error": "; ".join(result.errors)}

    return {
        "filename": info.get("filename", ""),
        "sheets": [
            {
                "name": s.name,
                "row_count": s.row_count,
                "col_count": s.col_count,
                "headers": s.headers,
            }
            for s in result.sheets
        ],
        "content": result.markdown,
        "truncated": result.truncated,
        "query": query,
    }


EXCEL_TOOLS = [
    ToolDefinition(
        name="extract_data",
        description=(
            "Extract structured data from an uploaded Excel or CSV file using "
            "a schema. Maps spreadsheet columns to output fields with type "
            "coercion. Returns rows as JSON objects. Use this when you need "
            "to import or process tabular data from a spreadsheet."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "UUID of the uploaded spreadsheet file.",
                },
                "schema": {
                    "type": "object",
                    "description": "Schema definition for extraction.",
                    "properties": {
                        "fields": {
                            "type": "array",
                            "description": (
                                "Field definitions. Each has: name (output field "
                                "name), type ('string'|'number'|'boolean'), "
                                "source_column (optional header to map from)."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {
                                        "type": "string",
                                        "enum": ["string", "number", "boolean"],
                                    },
                                    "source_column": {"type": "string"},
                                },
                                "required": ["name"],
                            },
                        },
                    },
                    "required": ["fields"],
                },
                "sheet_name": {
                    "type": "string",
                    "description": (
                        "Specific sheet to extract from (Excel only). "
                        "Omit to use the first/active sheet."
                    ),
                },
            },
            "required": ["file_id", "schema"],
        },
        handler=extract_data,
    ),
    ToolDefinition(
        name="analyze_spreadsheet",
        description=(
            "Analyze an uploaded Excel or CSV file. Returns sheet info "
            "(names, dimensions, headers) and a markdown representation "
            "of the data. Small sheets (<50 rows) get full tables; large "
            "sheets get summaries with stats. Use this to understand what "
            "data is in a spreadsheet before extracting."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "UUID of the uploaded spreadsheet file.",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "What to look for in the spreadsheet (e.g., "
                        "'What are the top customers by revenue?')."
                    ),
                },
                "sheet_name": {
                    "type": "string",
                    "description": "Specific sheet to analyze (Excel only).",
                },
            },
            "required": ["file_id"],
        },
        handler=analyze_spreadsheet,
    ),
]
