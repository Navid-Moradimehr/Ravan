# Contextual Help and SQL Workflow

Status: done
Last updated: 2026-07-09

## Why this note exists

The UI now uses small `?` help tips on ambiguous surfaces so users can see
where a control belongs without leaving the current page.

## What changed

- SQL Query now has inline guidance, a server-side timeout, and a Cancel button.
- Historian replay, trends, alarms/events, webhooks, notifications, and
  integration catalog cards now expose contextual help.
- Integration surfaces are split between:
  - editable in app
  - deployment-configured
  - catalog-only with setup guidance

## SQL workflow

1. User enters a read-only historian SQL statement.
2. The UI generates a query ID and submits the query through the Next.js proxy.
3. The historian service validates the SQL and applies `statement_timeout`.
4. Results return as rows and columns in the SQL panel.
5. If the user clicks Cancel, the UI sends a cancel request for the active query ID.

## Ownership boundaries

- SQL Query: historian read-only access, not a write path.
- Webhooks and Notifications: deployment/operator owned.
- Integrations catalog: documentation layer, not the editable control surface.
- Historian replay: validation and testing tool, not live plant control.

## Next checks

- Verify timeout and cancel behavior against real historian latency.
- Keep the help-tip copy short and aligned with the existing app typography.
- Reuse the same pattern for other dense cards only when the explanation is
  genuinely useful.
