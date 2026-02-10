"""Pydantic request/response schemas for Bitmod API.

Includes input validation constraints to prevent abuse.
"""

from pydantic import BaseModel, Field, field_validator

# --- Chat ---


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: user, assistant, system", max_length=20)
    content: str = Field(..., description="Message content", max_length=50000)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"user", "assistant", "system"}
        if v not in allowed:
            raise ValueError(f"role must be one of: {', '.join(allowed)}")
        return v


class ChatRequest(BaseModel):
    message: str = Field(..., description="User's message", min_length=1, max_length=10000)
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Conversation history",
        max_length=50,
    )
    filters: dict = Field(default_factory=dict, description="Query filters (jurisdiction, category, etc.)")
    stream: bool = Field(default=False, description="Whether to stream the response (opt-in)")
    project_id: str | None = Field(default=None, description="Project ID to scope knowledge context")


class PipelineStep(BaseModel):
    """One mechanism's decision in the cache pipeline."""

    mechanism: str = Field(..., description="Which mechanism ran (e.g., 'intent_detection', 'exact_cache')")
    action: str = Field(..., description="What it decided (e.g., 'HIT', 'MISS', 'SKIP')")
    detail: dict = Field(default_factory=dict, description="Mechanism-specific metadata")
    elapsed_ms: float = Field(0.0, description="Time spent in this step")


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = Field(default=0, description="Tokens served from cache (no LLM cost)")
    tokens_saved: int = Field(default=0, description="Estimated tokens saved vs a full LLM call")
    estimated_cost: float = Field(default=0.0, description="Estimated LLM cost in USD for this response")
    estimated_savings: float = Field(default=0.0, description="Estimated USD saved by cache hit")
    model_priced: str = Field(default="", description="Model used for cost estimation")
    pricing_updated: str = Field(default="", description="When pricing data was last updated (ISO 8601)")
    pricing_stale: bool = Field(default=False, description="True if pricing data is older than 7 days")


class ChatResponse(BaseModel):
    answer: str
    cached: bool = False
    cache_key: str | None = None
    sources: list[dict] = Field(default_factory=list)
    model_used: str | None = None
    generation_ms: int | None = None
    token_usage: TokenUsage | None = None
    pipeline_trace: list[PipelineStep] = Field(
        default_factory=list, description="Ordered log of every mechanism decision"
    )


# --- Search ---


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query", min_length=1, max_length=2000)
    jurisdiction: str | None = Field(default=None, max_length=100)
    document_type: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=10, ge=1, le=100)


class SearchResultItem(BaseModel):
    section_id: str
    citation: str
    title: str
    snippet: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total: int
    query: str


# --- Ingest ---


class IngestFileRequest(BaseModel):
    """Request to ingest a file by path (server-side files only)."""

    file_path: str = Field(..., description="Path to file on server", max_length=1000)
    document_type: str = Field(default="document", max_length=100)
    source: str = Field(default="upload", max_length=200)
    title: str | None = Field(default=None, max_length=500)
    jurisdiction: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20)
    metadata: dict = Field(default_factory=dict)
    chunk_size: int = Field(default=500, ge=100, le=5000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)


class IngestTextRequest(BaseModel):
    """Request to ingest raw text content."""

    text: str = Field(..., description="Text content to ingest", min_length=1, max_length=5_000_000)
    title: str = Field(default="Untitled", max_length=500)
    document_type: str = Field(default="text", max_length=100)
    source: str = Field(default="api", max_length=200)
    jurisdiction: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20)
    metadata: dict = Field(default_factory=dict)
    chunk_size: int = Field(default=500, ge=100, le=5000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)


class IngestResponse(BaseModel):
    document_id: str
    title: str
    source_format: str
    sections: int
    chunks: int
    blocks: int = 0
    tags: int = 0
    embedded: bool = False
    is_reingest: bool = False
    sections_updated: int = 0
    sections_unchanged: int = 0


# --- Project Knowledge System ---


class ProjectCreateRequest(BaseModel):
    """Register a project for knowledge tracking."""

    root_path: str = Field(..., description="Absolute path to project directory", max_length=2000)
    name: str | None = Field(default=None, description="Project name (defaults to directory name)", max_length=255)
    description: str = Field(default="", max_length=2000)


class ProjectResponse(BaseModel):
    id: str
    name: str
    root_path: str
    description: str = ""
    language: str = ""
    framework: str = ""
    is_active: bool = True
    file_count: int = 0
    total_chunks: int = 0
    last_scanned_at: str | None = None


class ProjectScanResponse(BaseModel):
    project_id: str
    files_scanned: int
    files_changed: int
    files_deleted: int
    chunks_created: int


class ConversationRateRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    feedback: str = Field(default="", max_length=5000)


class CorrectionRequest(BaseModel):
    corrected_answer: str = Field(..., min_length=1, max_length=50000)
    correction_type: str = Field(default="factual", max_length=50)

    @field_validator("correction_type")
    @classmethod
    def validate_correction_type(cls, v: str) -> str:
        allowed = {"factual", "incomplete", "outdated", "wrong_context", "formatting"}
        if v not in allowed:
            raise ValueError(f"correction_type must be one of: {', '.join(allowed)}")
        return v


class ConversationResponse(BaseModel):
    id: str
    project_id: str | None = None
    user_message: str
    assistant_response: str
    model_used: str = ""
    cache_hit: bool = False
    rating: int | None = None
    feedback: str | None = None
    generation_ms: int = 0
    created_at: str | None = None


class CorrectionResponse(BaseModel):
    id: str
    conversation_id: str | None = None
    project_id: str | None = None
    original_question: str
    corrected_answer: str
    correction_type: str
    created_at: str | None = None


class ContextRequest(BaseModel):
    """Request assembled context for a query."""

    query: str = Field(..., min_length=1, max_length=10000)
    project_id: str | None = None
    include_history: bool = True
    include_corrections: bool = True
    token_budget: int = Field(default=8000, ge=500, le=32000)


class ContextResponse(BaseModel):
    project_context: str = ""
    history_context: str = ""
    corrections_context: str = ""
    total_tokens: int = 0
    sources: list[dict] = Field(default_factory=list)


# --- Health ---


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str
