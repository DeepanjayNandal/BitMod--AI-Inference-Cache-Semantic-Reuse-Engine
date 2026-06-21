# ADR-003: YAML-Driven Intent and Role Configuration

## Status

Accepted

## Context

BitMod's chat service routes incoming queries through an intent detection layer that classifies what the user is asking for (e.g., code generation, document search, summarization, general conversation) and selects the appropriate processing pipeline and LLM role configuration.

Early prototypes hardcoded intents and role prompts directly in Python. This created several problems:

- Adding or modifying an intent required a code change, a test pass, and a redeployment.
- Non-developer team members (product managers, prompt engineers) could not adjust behavior without developer involvement.
- Intent definitions were scattered across multiple Python files, making it difficult to see the full routing table at a glance.

We need a system where intent definitions and role configurations are data, not code, so they can be extended and tuned independently of the application release cycle.

## Decision

Intents and roles are defined in YAML configuration files, loaded at startup and optionally hot-reloaded on file change.

- **Intent definitions** live in `core/bitmod/config/intents.yaml`. Each intent specifies a name, description, example queries (used for few-shot matching), and the pipeline steps to execute.
- **Role definitions** live in `core/bitmod/config/roles.yaml`. Each role specifies a system prompt template, temperature, and any provider-specific parameters.
- The intent router reads these YAML files at startup and builds an in-memory lookup structure. If `BITMOD_HOT_RELOAD=true`, a file watcher triggers re-parsing on change without restarting the service.
- YAML files are validated against Pydantic models on load. Invalid configuration fails fast with clear error messages rather than silently degrading.
- Default YAML files ship with the package. Users can override them by placing custom files in `~/.bitmod/config/` or by setting `BITMOD_CONFIG_DIR`.

## Consequences

**What becomes easier:**

- Adding a new intent is a YAML edit, not a code change. This lowers the barrier for prompt engineers and product teams to iterate on routing behavior.
- The full intent routing table is visible in a single file, making it easy to audit and review.
- Hot-reload enables rapid iteration in development and staging environments without service restarts.
- Custom deployments can override default intents without forking the codebase.

**What becomes harder or requires care:**

- YAML configuration errors are caught at load time, not compile time. A typo in an intent name or a missing required field will not surface until the service starts (or hot-reloads). Pydantic validation mitigates this but does not eliminate the class of errors entirely.
- Debugging intent routing requires looking at both the YAML files and the router code. When an intent is not matching as expected, the developer must check the YAML definition, the matching logic, and the runtime state. We mitigate this with structured logging that records which intent was matched and why.
- Hot-reload in production must be used carefully. A malformed YAML push could break routing for all users until corrected. The loader validates before swapping, rejecting invalid files and keeping the previous valid configuration active, but operators should still gate config changes through review.
- YAML files are less expressive than Python. Complex conditional logic (e.g., "use this intent only if the user has uploaded a document in the current session") still requires code-level customization in the router.
