---
name: Managed Flask workflow reloader
description: Process-management constraint for Flask apps running as Replit artifact services.
---

Artifact-managed Flask services should run as a single process under Waitress, with managed workflow restarts providing the reload boundary.

**Why:** Flask's reloader can race with managed restarts and transient file writes. Its development server also exited intermittently under artifact workflow supervision despite handling requests successfully.

**How to apply:** Start the Flask WSGI application with Waitress on `$PORT` and `0.0.0.0`. After server-side changes, restart the exact artifact workflow and verify its running state and HTTP response rather than relying on Flask auto-reload.