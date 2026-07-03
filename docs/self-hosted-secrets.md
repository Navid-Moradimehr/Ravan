# Self-Hosted Secrets And Network Guidance

Date: 2026-07-03

This project is open-source and self-hosted, so operators must provide their own secrets, TLS material, and network segmentation.

## What The Platform Should Do

- fail closed when a secret is missing in production mode
- keep secrets out of exported manifests and sample bundles
- accept credentials through environment variables, mounted files, or cluster secrets
- keep model endpoints configurable per site
- keep auth and RBAC local to the deployment
- expose health and diagnostics without requiring privileged secrets

## What Operators Should Provide

- JWT signing secret
- broker credentials
- database credentials
- model API keys or local model endpoints
- TLS certificates and keys
- secret storage backend
- firewall and subnet segmentation

## Docker

Use an `.env` file or secret mount for operator-owned values.

```bash
JWT_SECRET=replace-with-real-secret
TIMESCALE_PASSWORD=replace-with-real-password
LLM_API_KEY=replace-with-real-key
```

Recommended practice:

- keep the `.env` file outside source control
- mount secrets as read-only files when possible
- do not bake credentials into the image

## systemd

Use the generated `env/site.env` file as the operator-controlled secret injection point.

Recommended practice:

- store the environment file under `/etc/datastream/<project>/<site>/env/site.env`
- restrict the file to root or the service account
- keep broker/model credentials in a separate secret file if the environment should not be world-readable
- use `EnvironmentFile=` instead of hardcoding secrets in the unit

## Kubernetes

Use native `Secret` resources or an external secret operator.

Minimal pattern:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: data-stream-secrets
type: Opaque
stringData:
  JWT_SECRET: replace-with-real-secret
  TIMESCALE_PASSWORD: replace-with-real-password
  LLM_API_KEY: replace-with-real-key
```

Recommended practice:

- mount secrets as environment variables or projected volumes
- keep the generated Helm values free of live credentials
- replace the placeholder secret name with your cluster standard

## Minimum Trusted Zones

The platform should usually live inside at least three trust zones:

- edge/device network for PLCs and sensors
- plant runtime network for brokers, historians, and processing
- operator/admin network for UI, CLI, and release tooling

If there is a central federation layer:

- keep it read-mostly
- only replicate approved summaries or explicit bridge outputs
- avoid making central services mandatory for local plant operation

## Release Reminder

The default JWT placeholder is only safe for development and tests. Production releases should replace it before rollout.

