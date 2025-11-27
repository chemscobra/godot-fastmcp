from pydantic import BaseModel


class ContentItem(BaseModel):
    type: str
    text: str


class ToolResponse(BaseModel):
    content: list[ContentItem]
    is_error: bool = False
    model_config = {"populate_by_name": True}


class GodotServerConfig(BaseModel):
    godot_path: str | None
    godot_operations_script: str | None = None
    debug_mode: bool
    godot_debug_mode: bool
    strict_path_validation: bool
