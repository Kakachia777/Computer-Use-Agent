"""Collection classes for managing multiple tools."""

from typing import Any
import time

from anthropic.types.beta import BetaToolUnionParam

from .base import (
    BaseAnthropicTool,
    ToolError,
    ToolFailure,
    ToolResult,
)


class ToolCollection:
    """Optimized tool collection with caching and error handling."""

    def __init__(self, *tools: BaseAnthropicTool):
        self.tools = {tool.to_params()["name"]: tool for tool in tools}
        self._result_cache = {}
        self._cache_ttl = 60  # Cache results for 60 seconds

    async def run(self, *, name: str, tool_input: dict[str, Any]) -> ToolResult:
        """Execute tool with caching and error handling."""
        cache_key = f"{name}:{hash(str(tool_input))}"

        # Check cache
        if self._check_cache(cache_key):
            return self._result_cache[cache_key]

        tool = self.tools.get(name)
        if not tool:
            return ToolResult(error=f"Tool {name} not found")

        try:
            result = await tool(**tool_input)
            # Cache successful results
            if not result.error:
                self._cache_result(cache_key, result)
            return result

        except Exception as e:
            return ToolResult(error=str(e))

    def _check_cache(self, key: str) -> bool:
        """Check if valid cache entry exists."""
        if key not in self._result_cache:
            return False
        timestamp, _ = self._result_cache[key]
        return time.time() - timestamp < self._cache_ttl
