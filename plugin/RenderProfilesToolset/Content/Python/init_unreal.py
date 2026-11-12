"""Editor startup: register this plugin's MCP toolset with the Toolset Registry."""

import render_profiles_toolset_mcp
from toolset_registry.registration import Registration

_registration = Registration([render_profiles_toolset_mcp.RenderProfileTools])
_registration.register()
