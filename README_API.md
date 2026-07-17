# Ravan - API & New Features

## REST API Service (`services/api_service/main.py`)

A FastAPI-based service providing external integration endpoints.

### Running the API Service

```bash
# Direct
python services/api_service/main.py

# Docker
 docker compose --profile api up api-service
```

Port: `8020` (configurable via `API_SERVICE_PORT`)

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| POST | `/api/v1/historian/query` | Run SQL against TimescaleDB |
| GET | `/api/v1/historian/tables` | List available tables |
| GET | `/api/v1/historian/alarms` | Get active alarms |
| GET | `/api/v1/historian/trend` | Get tag trend data |
| GET | `/api/v1/historian/events` | Get raw events |
| GET | `/api/v1/assets` | Asset hierarchy |
| GET | `/api/v1/scenarios` | List scenarios |
| POST | `/api/v1/webhooks` | Register webhook |
| GET | `/api/v1/webhooks` | List webhooks |
| POST | `/api/v1/webhooks/test/{id}` | Test webhook |
| POST | `/api/v1/notifications` | Add notification channel |
| GET | `/api/v1/notifications` | List channels |
| POST | `/api/v1/users` | Create user (RBAC) |
| POST | `/api/v1/auth/login` | Mock login |
| GET | `/api/v1/audit-logs` | View audit log |

### SQL Query Example

```bash
curl -X POST http://localhost:8020/api/v1/historian/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM industrial_events LIMIT 5"}'
```

### Webhook Registration Example

```bash
curl -X POST http://localhost:8020/api/v1/webhooks \
  -H "Content-Type: application/json" \
  -d '{"url": "https://hooks.example.com/alerts", "events": ["alarm", "anomaly"]}'
```

## RBAC (Role-Based Access Control)

Roles: `admin`, `operator`, `viewer`

Permissions:
- `admin`: read, write, delete, admin
- `operator`: read, write
- `viewer`: read

All actions are logged to the audit log (`GET /api/v1/audit-logs`).

## UI Components

- **SQL Query Panel** — Ad-hoc SQL with live results table
- **Webhook Panel** — Register, test, and delete outbound webhooks
- **Notification Panel** — Configure email, Slack, and generic webhook alerts
- **Dashboard Builder** — Drag-and-drop custom panels (placeholder for full implementation)

## Mobile Responsiveness

The main layout now uses responsive grid breakpoints:
- Single column on mobile
- Sidebar + main content on tablet (`md:`)
- Full 3-column layout on desktop (`lg:`)

## Docker Compose

The `api-service` is available under the `api` profile:

```bash
docker compose --profile api up api-service
```

TimescaleDB service has been moved out of the `volumes` section to fix YAML structure.
