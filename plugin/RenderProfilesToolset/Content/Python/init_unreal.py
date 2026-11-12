"""Editor startup: register this plugin's MCP toolset with the Toolset Registry (same pattern as Epic's toolsets)."""

from toolset_registry.registration import Registration

import render_profiles_toolset_mcp

_registration = Registration([render_profiles_toolset_mcp.RenderProfileTools])
_registration.register()
