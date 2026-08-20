---
name: Managed Flask workflow reloader
description: Process-management constraint for Flask apps running as Replit artifact services.
---

Artifact-managed Flask services should run as a single process with Flask's built-in reloader disabled; managed workflow restarts provide the reload boundary.

**Why:** The reloader's child-process lifecycle can race with managed restarts and transient file writes, causing the workflow to finish or fail even when the source files are valid.

**How to apply:** After server-side changes, restart the exact artifact workflow and verify its running state and HTTP response rather than relying on Flask auto-reload.