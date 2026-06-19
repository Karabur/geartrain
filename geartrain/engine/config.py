"""Workspace and engine configuration models."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, Self, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, model_validator

SCHEMA_VERSION = 1
_NAME_PATTERN = r"^[a-z][a-z0-9-]*$"


# --- Shared base -----------------------------------------------------------

class _SchemaBase(BaseModel):
    """Base model with schema-version and name validation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    name: Annotated[str, Field(pattern=_NAME_PATTERN)]

    @model_validator(mode="after")
    def _check_schema_version(self) -> Self:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version {self.schema_version!r}; "
                f"expected {SCHEMA_VERSION}"
            )
        return self


# --- Workspace config ------------------------------------------------------

class ProjectConfig(BaseModel):
    """Project metadata inside workspace config."""

    model_config = ConfigDict(extra="forbid")
    name: str
    repo_root: str = "."
    knowledge_base: list[str] = []


class LlmWorkspaceConfig(BaseModel):
    """LLM defaults and model hints for the workspace."""

    model_config = ConfigDict(extra="forbid")
    default_provider: str
    default_model: str
    model_hints: dict[str, str] = {}


class WorkspaceRegistries(BaseModel):
    """Registry paths for agents and workflows."""

    model_config = ConfigDict(extra="forbid")
    agents: str
    workflows: str


class MemoryPaths(BaseModel):
    """Memory directory paths."""

    model_config = ConfigDict(extra="forbid")
    root: str
    workspace: str
    workflows: str
    agent_types: str


class IntegrationConfig(BaseModel):
    """Single integration entry (e.g. github)."""

    model_config = ConfigDict(extra="forbid")
    owner: str
    repo: str
    credential: str


class WorkspaceConfig(_SchemaBase):
    """Full workspace.yaml configuration."""

    description: str = ""
    project: ProjectConfig
    llm: LlmWorkspaceConfig
    registries: WorkspaceRegistries
    memory: MemoryPaths
    integrations: dict[str, IntegrationConfig] = {}


# --- Engine config ---------------------------------------------------------

class EngineWorkspaceRef(BaseModel):
    """Reference to a workspace config file."""

    model_config = ConfigDict(extra="forbid")
    path: str


class EngineLlmProvider(BaseModel):
    """Single LLM provider configuration."""

    model_config = ConfigDict(extra="forbid")
    api_key_env: str


class EngineLlmConfig(BaseModel):
    """Engine-level LLM configuration."""

    model_config = ConfigDict(extra="forbid")
    default: str
    providers: dict[str, EngineLlmProvider] = {}


class EngineStateConfig(BaseModel):
    """State persistence configuration."""

    model_config = ConfigDict(extra="forbid")
    backend: str
    path: str


class EngineResources(BaseModel):
    """Resource limits for the engine."""

    model_config = ConfigDict(extra="forbid")
    max_concurrent_workflows: int = 1
    max_concurrent_agents: int = 1


class EngineToolShell(BaseModel):
    """Shell tool configuration."""

    model_config = ConfigDict(extra="forbid")
    cwd: str = "."
    allow_network: bool = False
    timeout_seconds: int = 60


class EngineToolFilesystem(BaseModel):
    """Filesystem tool configuration."""

    model_config = ConfigDict(extra="forbid")
    root: str = "."


class EngineConfig(_SchemaBase):
    """Full engine.yaml configuration."""

    description: str = ""
    type: str = "local"
    host: str = "127.0.0.1"
    port: int = 8420
    workspace: EngineWorkspaceRef
    llm: EngineLlmConfig
    credentials: dict[str, Any] = {}
    state: EngineStateConfig
    resources: EngineResources = Field(default_factory=EngineResources)
    tools: dict[str, Any] = {}


# --- Agent definitions -----------------------------------------------------

class _BaseAgentConfig(BaseModel):
    """Shared base for agent type-specific configs."""

    model_config = ConfigDict(extra="forbid")
    type: str


class CliAgentConfig(_BaseAgentConfig):
    """Configuration for a cli-type agent."""

    type: Literal["cli"]
    command: str
    timeout_seconds: int = 300
    work_folder: str = "work"
    sandbox: str = "workspace-write"
    credential: str


class LangchainAgentConfig(_BaseAgentConfig):
    """Configuration for a langchain-type agent.

    The model is chosen by ``model_hint`` (resolved against workspace
    ``model_hints``) or by an explicit ``llm_provider``/``llm_model`` pair.
    When neither is set the workspace defaults apply. Credentials never live
    here — they come from the engine config.
    """

    type: Literal["langchain"]
    llm_provider: str | None = None
    llm_model: str | None = None
    model_hint: str | None = None
    tools: list[str] = []
    context_window: int = 8192
    guardrails: list[str] = []
    runtime: str = "sync"
    work_folder: str = "work"
    forbidden_paths: list[str] = []


def _agent_type_discriminator(value: Any) -> str:
    """Extract agent type for discriminated-union routing."""
    if isinstance(value, dict):
        return value.get("type", "")
    return getattr(value, "type", "")


AgentConfig = Annotated[
    Union[
        Annotated[CliAgentConfig, Tag("cli")],
        Annotated[LangchainAgentConfig, Tag("langchain")],
    ],
    Discriminator(_agent_type_discriminator),
]


class AgentMemoryScopes(BaseModel):
    """Memory read/write scopes for an agent."""

    model_config = ConfigDict(extra="forbid")
    read: list[str] = []
    write: list[str] = []


class AgentDefinition(_SchemaBase):
    """Full agent.yaml definition.

    Accepts ``type`` and the type-specific block (``cli`` or ``langchain``)
    at the top level of the YAML, then routes them into a typed ``config``
    field via a before-validator.
    """

    model_config = ConfigDict(extra="allow")

    description: str = ""
    config: AgentConfig
    system_prompt: str = ""
    memory: AgentMemoryScopes = Field(default_factory=AgentMemoryScopes)

    @model_validator(mode="before")
    @classmethod
    def _route_type_config(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        agent_type = data.pop("type", None)
        if agent_type and agent_type in data:
            raw_block = data.pop(agent_type) or {}
            data["config"] = {"type": agent_type, **raw_block}
        return data


# --- Workflow definitions --------------------------------------------------

# Trigger types the engine accepts as declarative metadata. The only runtime
# behavior is "run the workflow from its entry node"; the type records intent
# and gates unknown values. Add types here as real triggers are implemented.
KNOWN_TRIGGER_TYPES = ("manual",)


class WorkflowTrigger(BaseModel):
    """Workflow trigger configuration.

    ``type`` is declarative metadata, validated against ``KNOWN_TRIGGER_TYPES``.
    """

    model_config = ConfigDict(extra="forbid")
    type: str

    @model_validator(mode="after")
    def _check_type(self) -> Self:
        if self.type not in KNOWN_TRIGGER_TYPES:
            raise ValueError(
                f"unknown trigger type {self.type!r}; "
                f"expected one of {list(KNOWN_TRIGGER_TYPES)}"
            )
        return self


class WorkflowGraph(BaseModel):
    """Workflow execution graph definition."""

    model_config = ConfigDict(extra="forbid")
    entry: str
    nodes: dict[str, dict[str, Any]]


class WorkflowDefinition(_SchemaBase):
    """Full workflow.yaml definition."""

    description: str = ""
    version: str = "0.1.0"
    trigger: WorkflowTrigger
    channels: dict[str, str] = {}
    agents: dict[str, str] = {}
    graph: WorkflowGraph


# --- Memory entries --------------------------------------------------------

class MemoryScope(str, Enum):
    """Valid memory scope values."""

    WORKSPACE = "workspace"
    WORKFLOW = "workflow"
    AGENT_INSTANCE = "agent_instance"
    AGENT_LEVEL = "agent_level"


class MemoryEntry(BaseModel):
    """Memory entry parsed from YAML frontmatter."""

    model_config = ConfigDict(extra="forbid")
    scope: MemoryScope
    source: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    tags: list[str] = []


class MemoryReference(BaseModel):
    """Cross-reference to another memory entry."""

    model_config = ConfigDict(extra="forbid")
    entry_id: str
    relation: str = "related"
