# ADR 0004: ACL pre-filter plus row-level security

Status: accepted.

Materialize user/group/org principal strings on chunks so both candidate SQL branches can filter before ranking. Set transaction-local user, organization, and group context and enforce the matching rule through forced Postgres RLS. Defense in depth is intentional: neither Python post-filtering nor a later citation check can undo content exposure caused by ranking unauthorized chunks.
