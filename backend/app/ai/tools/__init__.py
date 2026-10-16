"""Tool registry for AI function calling.

Every tool wraps an existing service method. Tools are registered in this
module so the AI service can expose them to the model during function calling.

Tool rules (``docs/08-AI_ARCHITECTURE.md`` §6):
- Every tool wraps an existing service method.
- Tool arguments are validated against a Pydantic schema before service invocation.
- Tool execution runs under the calling user's identity — same permission checks apply.
- No tool can escalate privileges, bypass tenancy, or write raw SQL.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from app.ai.providers.base import ToolDefinition

logger = structlog.get_logger(__name__)


# Type alias for a tool handler: receives parsed arguments and returns JSON.
ToolHandler = Callable[..., Coroutine[Any, Any, Any]]


class ToolRegistry:
    """Registry that maps tool names to their definitions and handler functions.

    Usage::

        from app.ai.tools import registry as tool_registry
        from app.ai.providers.base import ToolDefinition

        tool_registry.register("lookup_appointments", definition, handler_fn)
        tools = tool_registry.get_definitions()  # list of ToolDefinition
    """

    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(
        self,
        name: str,
        definition: ToolDefinition,
        handler: ToolHandler,
    ) -> None:
        """Register a tool with its definition and handler.

        :param name: Unique tool name.
        :param definition: The tool's JSON schema definition.
        :param handler: An async callable that implements the tool.
        """
        self._definitions[name] = definition
        self._handlers[name] = handler
        logger.debug("tool_registered", name=name)

    def get_definition(self, name: str) -> ToolDefinition | None:
        """Get a tool's schema definition.

        :param name: The tool name.
        :returns: The :class:`ToolDefinition`, or ``None``.
        """
        return self._definitions.get(name)

    def get_definitions(self) -> list[ToolDefinition]:
        """Return all registered tool definitions for model function calling.

        :returns: List of all :class:`ToolDefinition` instances.
        """
        return list(self._definitions.values())

    def get_handler(self, name: str) -> ToolHandler | None:
        """Get the handler function for a tool.

        :param name: The tool name.
        :returns: The handler, or ``None``.
        """
        return self._handlers.get(name)

    async def execute(self, name: str, **kwargs: Any) -> Any:
        """Execute a registered tool with validated arguments.

        :param name: The tool name.
        :param kwargs: Parsed tool arguments.
        :returns: The tool's result.
        :raises KeyError: If the tool is not registered.
        """
        handler = self._handlers.get(name)
        if handler is None:
            msg = f"Tool '{name}' is not registered."
            raise KeyError(msg)
        return await handler(**kwargs)

    @property
    def available_tools(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._definitions.keys())


# Module-level singleton.
registry = ToolRegistry()


__all__ = [
    "ToolHandler",
    "ToolRegistry",
    "registry",
]
