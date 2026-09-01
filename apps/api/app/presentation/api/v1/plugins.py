from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.core.plugins.plugin_runtime import (
    PluginRuntimeEngine, PluginManifest, PluginState, PluginStatus, PluginSandboxExecutionResult
)

router = APIRouter(prefix="/plugins", tags=["Production Sandboxed Plugin Runtime"])

class InstallPluginRequest(BaseModel):
    plugin_id: str
    name: str
    version: str = "1.0.0"
    author: str = "Community Developer"
    description: str
    permissions: List[str] = ["crm:read"]

class ExecutePluginRequest(BaseModel):
    action_name: str
    payload: Dict[str, Any]

@router.get("", response_model=List[PluginState])
async def list_installed_plugins():
    """Lists all installed plugins and their isolation health status."""
    return PluginRuntimeEngine.list_plugins()

@router.post("/install", response_model=PluginState, status_code=status.HTTP_201_CREATED)
async def install_plugin_endpoint(
    req: InstallPluginRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """Installs and validates a new plugin manifest in the isolated Plugin Runtime Engine."""
    try:
        manifest = PluginManifest(
            plugin_id=req.plugin_id.lower(),
            name=req.name,
            version=req.version,
            author=req.author,
            description=req.description,
            permissions=req.permissions
        )
        return PluginRuntimeEngine.register_plugin(manifest)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plugin_id}/enable", response_model=PluginState)
async def enable_plugin_endpoint(
    plugin_id: str,
    current_broker: Broker = Depends(get_current_broker)
):
    """Enables an installed plugin."""
    try:
        return PluginRuntimeEngine.set_plugin_status(plugin_id.lower(), PluginStatus.ENABLED)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{plugin_id}/disable", response_model=PluginState)
async def disable_plugin_endpoint(
    plugin_id: str,
    current_broker: Broker = Depends(get_current_broker)
):
    """Disables an installed plugin."""
    try:
        return PluginRuntimeEngine.set_plugin_status(plugin_id.lower(), PluginStatus.DISABLED)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{plugin_id}/execute", response_model=PluginSandboxExecutionResult)
async def execute_plugin_endpoint(
    plugin_id: str,
    req: ExecutePluginRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """Safely executes a plugin hook inside an isolated sandbox catch-block."""
    return PluginRuntimeEngine.execute_plugin_safely(
        plugin_id=plugin_id.lower(),
        action_name=req.action_name,
        payload=req.payload
    )
