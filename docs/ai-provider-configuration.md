# AI Provider Configuration

The AI gateway keeps the platform contract stable while allowing operators to
choose a local model server, an OpenAI-compatible cloud endpoint, or native
Anthropic/Gemini APIs. The platform does not require a cloud model and does not
store provider secrets in source metadata, the historian, Kafka, or the UI.

## Configure After Installation

For Docker Compose, copy `.env.example` to `.env`, edit the `LLM_*` values, and
restart the gateway:

```powershell
docker compose -f docker/docker-compose.yml up -d --build ai-gateway
```

For a direct service launch, set the same variables in the service account
environment. For Kubernetes, put `LLM_API_KEY` in a Kubernetes Secret and
inject it into the AI gateway; keep non-secret values in a ConfigMap or site
profile. Never commit `.env` or a Secret containing a real key.

| Variable | Meaning |
|---|---|
| `LLM_PROVIDER` | `openai`, `openai_compat`, `anthropic`, `gemini`, `deepseek`, `qwen`, `kimi`, `glm`, `ollama`, or `disabled` |
| `LLM_ENDPOINT_URL` | Provider base URL; override for regional/private gateways |
| `LLM_API_KEY` | Provider credential, supplied by the operator |
| `LLM_MODEL_ID` | Provider model identifier |
| `LLM_MAX_OUTPUT_TOKENS` | Native-provider output limit; default `2048` |
| `LLM_LOCAL_ONLY` | Reject public endpoints when `true` |

Named provider defaults are Anthropic (`https://api.anthropic.com`, native
Messages API), Gemini (`https://generativelanguage.googleapis.com`, native
`generateContent` API), DeepSeek (`https://api.deepseek.com`), Qwen/DashScope
(`https://dashscope.aliyuncs.com/compatible-mode/v1`), Kimi/Moonshot
(`https://api.moonshot.ai/v1`), GLM/Zhipu
(`https://open.bigmodel.cn/api/paas/v4`), and OpenAI
(`https://api.openai.com/v1`). DeepSeek, Qwen, Kimi, GLM, and OpenAI use the
OpenAI-compatible chat-completions contract. Ollama keeps its local `/api/chat`
contract. Regional, enterprise, or proxy endpoints override the default URL.

Use `openai_compat` for vLLM, LM Studio, and any other server implementing
`/chat/completions`. The gateway exposes `GET http://localhost:8080/providers`
for a safe provider catalog and current non-secret status; it never returns an
API key.

## Reports And Outputs

The **AI Reporting** page at `/ai-reporting` saves policies and shows queued,
completed, and failed job status, attempts, time windows, and errors. A manual
request creates a report job and does not perform a plant-control action.

Generated reports are published as versioned events on Kafka topic
`iot.ai_enriched` and persisted by the AI-enriched fan-out in historian table
`ai_enriched`. Operators can inspect them in Kafka UI, query them through the
Historian SQL panel, or visualize them in Grafana. The job table intentionally
shows bounded job metadata rather than unbounded model text; Kafka and the
historian are the durable report record.

Provider timeouts, non-2xx responses, invalid shapes, and structured-output
failures mark the gateway degraded. With fallback enabled, a deterministic
industrial summary is emitted and records the fallback reason. With fallback
disabled, the bounded job is retried.
