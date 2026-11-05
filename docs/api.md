# API notes

Base path: `/api/v1`. Protected routes use `Authorization: Bearer <access-token>`.

Interactive schema and request testing are available at `http://localhost:8000/docs` after starting Compose.

## Authentication

- `POST /auth/login` accepts `{ "email", "password" }` and returns access and refresh tokens plus profile.
- `POST /auth/refresh` accepts `{ "refresh_token" }` and issues a new pair.
- `GET /auth/me` returns the active profile.

Example login and streamed chat request:

```sh
TOKEN=$(curl -fsS http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@acme-demo.com","password":"demo-pass-123"}' | jq -r .access_token)

curl -N http://localhost:8000/api/v1/chat/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{"question":"Which cities does the Strategy group prioritize for Midwest pilots?"}'
```

The response is an SSE stream with `meta`, one or more `token` events, a validated `citations` event, and a final `done` event.

## Documents

- `GET /documents` returns only documents visible to the caller.
- `POST /documents` accepts multipart `file` and `visibility`; returns 202 with the current ingestion state.
- `POST /documents/{id}/versions` accepts a replacement multipart file and creates a new version.
- `GET /documents/{id}` and `/file` return authorized metadata or content.
- `GET /documents/{id}/chunks/{chunk_id}` verifies the document and chunk under the same ACL before showing passage text.
- `PUT /documents/{id}/acl` accepts `{ "visibility", "grants": [{"principal_type":"group|user", "principal_id":"uuid"}] }`.
- `POST /documents/{id}/retry` queues ingestion; `DELETE /documents/{id}` soft-retires it.

## Chat

`POST /chat/ask` accepts `{ "question", "conversation_id"?, "deep_search": false }` and responds as server-sent events. Events arrive as `meta` (conversation/message IDs), `token` (text fragments), `citations` (final citation array), and `done`. The citation object carries marker, chunk/document IDs, title, page range, heading path, snippet, score, and viewer URL.

Conversation list/detail and `POST /chat/messages/{id}/feedback` are available under `/chat`.

## Admin and health

Admin-only: `/admin/overview`, `/admin/users`, `/admin/groups`, and `POST /admin/groups`. Health endpoints are `/health/live` and `/health/ready`; Prometheus scrape endpoint is `/metrics`.
