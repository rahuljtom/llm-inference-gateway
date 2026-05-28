# LLM Gateway Reliability Lab — 90-Second Loom Demo Script

**Target Audience:** Engineering Managers, Recruiters, Systems Engineers
**Tone:** Technical, infrastructure-focused, authoritative.

---

### [0:00 - 0:15] The Hook & Request Flow
**Visual**: Show the React Dashboard. Type a prompt and hit send.
**Action**: Point out the "Pipeline Tracer" in the Observability Panel as it lights up.
**Script**: 
> "Building AI applications is no longer just about prompting; it's about systems engineering. This is the LLM Inference Gateway. I just dispatched a request, and you can see our pipeline trace intercept the call, check Redis for rate limits, route the request dynamically to Groq, and stream the Server-Sent Events back in real time."

### [0:15 - 0:35] Observability & Dashboard Telemetry
**Visual**: Hover over the Latency chart and the Token Velocity (tk/s) metrics.
**Action**: Show the admin telemetry panel.
**Script**:
> "Because we proxy all traffic, we have absolute observability. Here on the dashboard, we track precise p95 latencies and token generation velocity. More importantly, we calculate the exact USD cost of every request based on the models used, logging all of this asynchronously to PostgreSQL."

### [0:35 - 0:55] Provider Failure Simulation & Fallback Recovery
**Visual**: Terminal/Code showing `SIMULATE_PROVIDER_FAILURE=true`. Go back to UI, send a request.
**Action**: UI shows a 3-second delay, the primary provider fails, and the fallback activates seamlessly.
**Script**: 
> "What happens when an upstream provider goes down? I've injected a synthetic failure simulating a complete provider outage. Watch the request—our gateway hits the 3-second timeout, catches the exception, and gracefully falls back to Anthropic in the background. The user still gets their answer, zero downtime."

### [0:55 - 1:15] Distributed Rate Limiting & Streaming
**Visual**: Show the Redis backend code or terminal logs rejecting a request with a 429.
**Action**: Send a massive block of text to trigger TPM (Tokens Per Minute) limit.
**Script**:
> "To protect our upstream API keys from bans, we estimate token counts pre-flight. If a tenant exceeds their Tokens Per Minute quota, the gateway enforces a local 429 Too Many Requests via Redis, protecting the infrastructure. When requests *are* successful, we normalize the streaming chunks across OpenAI, Gemini, and Anthropic into a single unified schema."

### [1:15 - 1:30] Benchmark Summary & Outro
**Visual**: Show the Benchmark Table from the `README.md` or Report.
**Action**: Highlight the 8ms routing overhead.
**Script**: 
> "The result is a highly available, robust control plane. We achieve full provider abstraction and retry resilience with just an 8-millisecond routing overhead. You can scan the QR code to read the full Reliability Lab technical report. Thanks for watching."
