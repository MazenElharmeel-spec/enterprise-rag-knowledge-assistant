# Synthetic demo corpus

These short examples were written for this project. They do not contain real company data, real customers, or personal information. The seed script assigns different access scopes so the permission behavior can be demonstrated safely.

| File | Seeded scope | Demonstrates |
|---|---|---|
| `expansion-overview.md` | Organization | Sources visible to both demo members |
| `strategy-notes.md` | Strategy group | A group-restricted source visible to Alice and the admin |
| `project-phoenix.md` | Alice only | An owner-private source |

Demo credentials are documented in the root README and are only for the local sample deployment. Replace them and the placeholder JWT secret before exposing a deployment to a network.
