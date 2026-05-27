# LLM Inference Gateway: Comprehensive System Overview

This document provides an exhaustive breakdown of the **LLM Inference Gateway**, detailing its architecture, features, evolution from its initial conceptualization (v0) to the current production-grade implementation, API surface, observability, and tracking metrics.

---

## 1. Core Architecture

The LLM Inference Gateway is an intermediary control plane that sits between internal client applications and external Large Language Model (LLM) providers (OpenAI, Anthropic, Gemini, Groq). It is designed to intercept inference requests, apply policies (auth, routing, rate-limiting, caching), and seamlessly proxy the requests to the desired upstream provider.

### 1.1 Backend Stack
- **Framework**: FastAPI (Python) for high-throughput, asynchronous request handling.
- **Database**: PostgreSQL (via SQLModel / asyncpg) for persistent storage of API keys, routing configurations, and request telemetry.
- **Cache & State**: Redis for distributed caching of inference responses and tracking rate-limit counters (Requests Per Minute & Tokens Per Minute).
- **HTTP Client**: `httpx.AsyncClient` for executing asynchronous, non-blocking requests to upstream providers.

### 1.2 Frontend Stack
- **Framework**: React + Vite for a blazing-fast SPA (Single Page Application) experience.
- **Styling**: TailwindCSS v4 with a custom premium theme, leveraging glassmorphism, backdrop filters, and neon accents.
- **Animations**: Framer Motion for smooth UI transitions, micro-animations, and chat bubble staggering.
- **Data Visualization**: Recharts for rendering real-time telemetry metrics (e.g., Latency timeseries charts).
- **Markdown & Highlighting**: `marked` and `highlight.js` for rendering code blocks and formatted AI responses.

---

## 2. Evolution: From v0 to Current Implementation

### The v0 / MVP State
- **Simple Proxying**: Hardcoded routing to one or two providers.
- **Basic Auth**: Global static API key or no authentication.
- **No Persistence**: Telemetry was logged to `stdout` without long-term tracking.
- **Basic UI**: Simple HTML/Vanilla JS interface for dispatching prompts, hosted directly from FastAPI templates.
- **Fragility**: Brittle error handling resulting in process crashes if provider credentials were omitted.

### The Current Production State (v3)
- **Dynamic Provider Registry**: Clean abstraction (`BaseProvider`) supporting OpenAI, Anthropic, Gemini, and Groq natively with streaming support.
- **Intelligent Routing & Fallbacks**: Auto-routing based on requested models, with robust fallback triggers to secondary providers if the primary times out or fails (HTTP 5xx, HTTP 429).
- **Hardened Resiliency**: Exponential backoff and retry mechanisms added directly into the provider resolution pipeline to survive upstream rate limits.
- **Database-Backed Auth**: Secure authentication resolving incoming Bearer tokens against hashed keys stored in PostgreSQL.
- **Granular Rate Limiting**: Distributed Redis-backed rate limiting enforcing both RPM (Requests Per Minute) and TPM (Tokens Per Minute) per API key.
- **Production UI**: A complete React rewrite separating the frontend into a modular, highly observable Dashboard (Sidebar, Header, ChatWorkspace, ObservabilityPanel).

---

## 3. Comprehensive Feature Set

### 3.1 Routing Engine
- **Manual Override**: Clients can strictly declare their provider via the `X-Provider` header.
- **Auto Routing**: If no provider is explicitly set, the gateway inspects the model name (e.g., `llama-3`) and automatically routes to the best-fit provider (e.g., `groq`).
- **Bring Your Own Key (BYOK)**: Clients can inject their own upstream provider keys dynamically via the `X-Provider-Api-Key` header or `api_key` payload property, overriding the Gateway's managed keys.

### 3.2 High-Availability (Fallbacks & Retries)
- **Retry Logic**: Automatic exponential backoff retries for timeout exceptions and HTTP 429 (Too Many Requests).
- **Fallback Node**: If a provider continuously fails or times out, the gateway seamlessly fails over to a secondary provider designated by the `X-Gateway-Fallback` header (or configured in the request body payload).

### 3.3 Semantic Caching
- **Redis Cache Layer**: Bypasses the upstream LLM entirely for exact-match or semantically identical prompt contexts.
- **Cache Keys**: Keys are aggressively hashed against the client ID, requested model, provider, and payload content.
- **Headers**: Injects `X-Cache-Hit: HIT|MISS` into the response headers.

### 3.4 Rate Limiting & Quotas
- **Pre-flight Estimation**: Uses a tokenizer estimation function to guess the token consumption of a payload before dispatching it.
- **Enforcement**: Checks Redis for RPM/TPM availability and issues standard `429 Too Many Requests` responses with `Retry-After`, `X-RateLimit-Remaining`, and `X-RateLimit-Limit` headers.
- **Post-flight Reconciliation**: Reconciles the estimated tokens with the actual upstream usage data returned by the LLM, updating the Redis counters accurately.

---

## 4. Observability & Tracking

The Gateway is designed with extreme observability in mind, capturing deep telemetry across every layer of the proxy.

### 4.1 Telemetry Pipeline (`app.middleware.logging.LoggingMiddleware`)
Every non-exempt request is intercepted post-completion, and the following metrics are flushed to the PostgreSQL `RequestLog` table asynchronously:
- `api_key_id`: The client that made the request.
- `provider` & `model`: Where the request was routed.
- `latency_ms`: Exact duration from ingress to egress.
- `prompt_tokens` & `completion_tokens`: Usage statistics extracted directly from the upstream provider's `[DONE]` or final JSON payload.
- `cost_usd`: Calculated expenditure based on the token usage and the specific model's pricing tier.
- `cached` & `fallback_used`: Booleans tracking optimization and high-availability triggers.

### 4.2 Admin & Control Plane APIs
A dedicated router (`/admin/api`) surfaces this aggregated telemetry to the dashboard:
- `GET /admin/api/stats`: Returns aggregated 24-hour request counts, cache hit ratios, fallback rates, total tokens consumed, and hourly distribution buckets.
- `GET /admin/api/providers`: Exposes real-time SLA metrics, latencies, and operational status of all active provider nodes.
- `GET /admin/api/metrics`: Delivers time-series metrics formatted for the React frontend's Recharts UI (throughput & latency).
- `GET /admin/api/health`: Validates connectivity to Postgres and Redis.

### 4.3 Frontend Observability Panel
The `ObservabilityPanel.jsx` provides a real-time command-center view to the user:
- **Request Pipeline Tracer**: Illuminates the current stage of the request (Client -> Gateway -> LLM) in real-time.
- **Latency Chart**: Renders an area-chart timeline of request response times, calculating the running average latency.
- **Per-Token Velocity**: In the chat workspace, response bubbles log exactly how many tokens were received and calculate the tokens-per-second (tk/s) generation speed for streaming responses.

---

## 5. API Surface

The system supports strict OpenAI-compatibility, meaning any standard OpenAI client SDK (Python, Node) can simply swap its `base_url` to point at the gateway.

### Chat Completions Ingress
`POST /v1/chat/completions`
Accepts a standard OpenAI payload with Gateway-specific extensions.

**Custom Gateway Headers:**
- `Authorization: Bearer <GATEWAY_API_KEY>` (Required)
- `X-Provider: groq|anthropic|openai|gemini` (Optional)
- `X-Gateway-Fallback: <provider>` (Optional)
- `X-Provider-Api-Key: <upstream_key>` (Optional - BYOK)

**Response Extensions:**
- `X-Cache-Hit`: Indicates if the response was served from Redis.
- `X-Gateway-Fallback`: Indicates if the request failed over to the fallback provider.
