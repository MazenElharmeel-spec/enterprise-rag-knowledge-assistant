# ADR 0002: Structure-aware chunks

Status: accepted.

Parse documents to blocks with page and heading metadata before splitting. Keep whole tables together, split long prose on sentence boundaries, group blocks up to the configured token limit, and retain a configurable overlap. Store page range, heading hierarchy, and character offsets with each chunk for citations. This is preferred over fixed character windows because page and section context matters to both answer quality and the viewer.
