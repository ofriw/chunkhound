# Purpose & positioning
A local-first “code-grep on steroids”: watches any directory, slices code into semantic units, stores them in an embedded DuckDB database with vector + regex search. Drop-in pluggable embeddings let teams choose the cheapest / fastest model day-to-day while keeping their index portable.

# Tech-stack at a glance

| Concern       | Chosen tech                          | Why                                                          |
| ------------- | ------------------------------------ | ------------------------------------------------------------ |
| Core language | Python 3.12                          | Fastest prototyping path; giant ML ecosystem.                |
| Storage & ANN | DuckDB 0.10.x + vss extension (HNSW) | Embedded, zero-config, ~Postgres-speed; HNSW index built-in. |
| Code parsing  | tree-sitter-languages wheels         | Pre-built grammars; no C toolchain hassle.                   |
| File watching | watchfiles 1.x                       | Rust-powered, cross-platform, async.                         |
| MCP Protocol  | FastMCP + stdin/stdout               | Model Context Protocol for AI assistant integration.          |
# Runtime topology
  ```mermaid
  flowchart TB
    %% ---------- external stimulus ----------
    subgraph " "
        style dir fill:#ffffff00,stroke:#ffffff00
        dir[Monitored&nbsp;Directory]
    end

    %% ---------- processes ----------
    subgraph "Runtime Processes"
        direction TB
        CLI["mcp CLI<br/>(entry point)"]
        Watcher["FS Watcher"]
        Parser["Parser<br/>(tree-sitter)"]
        Chunker["Chunker<br/>(funcs / classes / blocks)"]
        Embedder["Embedder<br/>(dynamic provider)"]
        DB["DuckDB<br/>(tables + HNSW)"]
        MCP["MCP Server<br/>(FastMCP)"]
        Query["Query Engine<br/>(vector &amp; regex)"]
    end

    %% ---------- data/event flow ----------
    dir -. file events .-> Watcher
    CLI -->|boot| Watcher
    Watcher -->|new / changed&nbsp;file| Parser
    Parser --> Chunker
    Chunker --> Embedder
    Embedder --> DB

    CLI --> API
    API --> Query
    Query --> DB
```




# Database schema (provider-aware)

  ```sql
CREATE TABLE files (

  id BIGINT PRIMARY KEY,

  path TEXT UNIQUE,

  mtime TIMESTAMP,

  language TEXT

);



CREATE TABLE chunks (

  id BIGINT PRIMARY KEY,

  file_id BIGINT REFERENCES files(id),

  symbol TEXT,

  start_line INT,

  end_line INT,

  code TEXT

);



CREATE TABLE embeddings (

  chunk_id BIGINT REFERENCES chunks(id),

  provider TEXT,     -- "openai" | "voyage" | 3rd-party

  model TEXT,        -- e.g. "text-embedding-3-small"

  dims  INT,

  vector FLOAT[]     -- fixed-length

);

-- convenience UDF builds an HNSW index per (provider,model,dims)
CALL mcp.create_hnsw('openai','text-embedding-3-small',1536,'cosine');
```

# Embedding subsystem (dynamic)

## Interface
```python
class EmbeddingProvider(Protocol):

    name: str

    model: str

    dims: int

    distance: str  # 'cosine' | 'l2'

    batch: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```
Providers register via `entry_points="mcp_embeddings"` so a simple `uv pip install` makes it discoverable.
## Built-ins

| Provider           | Default model          | Dims           | Required env / CLI                  |
| ------------------ | ---------------------- | -------------- | ----------------------------------- |
| openai             | text-embedding-3-small | 1536           | CHUNKHOUND_EMBEDDING_API_KEY / CHUNKHOUND_EMBEDDING_BASE_URL    |
| claude (Voyage AI) | voyage-3.5-lite        | 1024 (default) | VOYAGE_API_KEY or AWS Bedrock creds |
Flag `--model` overrides defaults; vectors are stored side-by-side, so you can **swap providers without re-indexing**—MCP backfills any missing vectors lazily.
# CLI & config


```bash
$ mcp run <path> \

      --db ~/.cache/mcp.duckdb \

      --provider openai \

      --model text-embedding-3-small \

      --api-key $CHUNKHOUND_EMBEDDING_API_KEY \

      --host 127.0.0.1 --port 7474
```
Common flags: `--include`/`--exclude`, `--debounce-ms`, `--batch`, `--rate`.

Optional `mcp.toml` is hot-reloaded.
# API surface

|        |                    |                              |                                                   |
| ------ | ------------------ | ---------------------------- | ------------------------------------------------- |
| Method | Route              | Params                       | Notes                                             |
| `GET`  | `/search/semantic` | `q, top_k, provider, filter` | Returns NDJSON stream, ranked by distance_cosine. |
| `GET`  | `/search/regex`    | `pattern, lang`              | SQL REGEXP_MATCH() under the hood.                |
| `POST` | `/admin/reindex`   | `body: {paths:[...]}`        | Force rebuild subset.                             |

OpenAPI schema auto-exposed at `/docs`.
# Performance targets (dev-laptop)
- **Index throughput**: 2 k LOC /s
- **Query p99**: < 50 ms for top-10 vector search on 100 k chunks
- **FS latency**: changes visible ≤ 2 s
- **Memory**: ~500 MB for 100 k × 1536-D vectors
# Security & ops
- No outbound calls unless embeddings are enabled.
- API keys read once, never logged, redacted from `/proc/<pid>/cmdline`.
- Uses DuckDB’s single-file DB → trivial backup & portability.
- Structured logs (loguru JSON) pipe to stdout—works with Docker or systemd.
# Roadmap notes
- Hybrid BM25 + vector ranking via DuckDB UDFs (future toggle).
- Editor plug-ins (LSP) reuse the same HTTP endpoints.
- Potential WASM build for in-browser docs search.
- When Anthropic ships a native embedding model, swap the “claude” provider to point at it without DB changes.
