# AI LM Studio Soak 2026-07-14

The local LM Studio model `openai/gpt-oss-20b` was reachable at
`192.168.100.7:1234`. A five-minute three-source stream sent 900 events. The
gateway consumed them without producer failure.

The final controlled warning run validated the complete path:

```text
warning events -> sustained tracker -> ai_report_jobs
                -> LM Studio -> iot.ai_enriched -> historian/AI UI
```

The accepted model response had `used_fallback=false` and 19.93s latency. The
8-second default produced deterministic fallback for the same class of larger
prompt, so deployment owners must size the model timeout for their local GPU.

The current single consumer waits synchronously for inference. Kafka provides
durability, but the next scalability step is a bounded report worker queue.
