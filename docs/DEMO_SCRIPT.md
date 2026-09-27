# 3–5 minute demo script

Prepare: `docker compose up --build`, open UI and Swagger, and keep a terminal at the repository root.

1. **Login / roles (20s):** sign in as admin. Point out role in the sidebar; mention the operator account cannot mutate cameras/watchlists.
2. **Onboarding (25s):** Cameras → Add camera; enter `DEMO-020`, “Airport Road Demo”, department “Traffic Police”, zone “East”, coordinates `23.0734`, `72.6266`. Submit and show it in search.
3. **Registry and GIS (20s):** show camera health, source type, heartbeat, and markers. Explain raw stream endpoints are not returned.
4. **Two feeds (25s):** Operations; show two independently moving synthetic feeds. Open one. Say “near-live generated adapter, explicitly not a physical stream.”
5. **Health update (20s):** Swagger `POST /cameras/{id}/heartbeat` with `degraded`; show the UI update over WebSocket.
6. **Analytics event (20s):** run `python scripts/simulate_events.py --vehicle GJ01XX0001`.
7. **Match + push (15s):** keep the dashboard visible; point to the immediate toast, counter and persisted critical alert.
8. **Respond (20s):** acknowledge, then resolve. State that actor and timestamps persist and are broadcast.
9. **Movement (30s):** Movement → search `GJ01XX0001`; show oldest-first three-camera timeline and polyline. Explicitly say it connects observations, not roads.
10. **Swagger workflow (25s):** show `/docs`, schemas, validation, and the ingestion result/duplicate behavior.
11. **Audit (15s):** show login, camera, heartbeat, event and response actions.
12. **Architecture / scale (30s):** open architecture diagram; explain edge/regional processing, Kafka partitions, central metadata, and why 160 Gb/s primary video is not centralized.

After recording, add candidate name/contact, GitHub URL, hosted URL and recording URL to the submission. Never show `.env` or connection secrets.

