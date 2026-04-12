"""
agents package — Tee-Mo pydantic-ai agent factory (STORY-007-02).

Exports:
    build_agent:  Async factory that constructs a fully configured pydantic-ai Agent
                  for the given workspace, resolving BYOK keys and injecting skill tools.
    AgentDeps:    Dependency container (dataclass) passed as deps_type to Agent().
"""

from app.agents.agent import AgentDeps, build_agent

__all__ = ["build_agent", "AgentDeps"]
