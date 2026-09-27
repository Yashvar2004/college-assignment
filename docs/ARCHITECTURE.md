# Architecture

## System context

```mermaid
flowchart LR
  subgraph Sources[Camera and video sources]
    SIM[Synthetic/recorded adapter]
    RTSP[Future RTSP / ONVIF / HLS / WebRTC]
  end
  SIM --> AD[Source adapter interface]
  RTSP -. plug-in .-> AD
  AD --> VID[Video delivery / player]
  AD --> HB[Heartbeat workflow]
  AD --> AI[Analytics inference output]
  AI --> ING[Validated ANPR ingestion]
  HB --> API[FastAPI service]
  ING --> API
  API --> MATCH[Normalization + watchlist matching]
  MATCH --> PG[(PostgreSQL)]
  API --> PG
  API --> REDIS[(Redis / future pub-sub and rate state)]
  MATCH --> ALERT[Persisted alert]
  ALERT --> WS[Authenticated WebSocket layer]
  WS --> DASH[React command-center dashboard]
  VID --> DASH
  PG --> GIS[Movement query + GIS points]
  GIS --> MAP[Leaflet / OpenStreetMap]
  MAP --> DASH
  API --> AUDIT[Audit logging]
  AUDIT --> PG
```

PostgreSQL is the source of truth. Event ingestion validates bounds/confidence/identity, normalizes the plate, checks exact external ID and a 10-second camera/plate fingerprint, persists, matches active valid watchlist rows, and commits before broadcasting. Response schemas deliberately omit `stream_endpoint_secret`.

## Entity model

```mermaid
erDiagram
  USER ||--o{ AUDIT_LOG : acts
  USER ||--o{ ALERT : acknowledges
  CAMERA ||--o{ DETECTION_EVENT : observes
  CAMERA ||--o{ ALERT : raises_at
  WATCHLIST ||--o{ ALERT : matches
  DETECTION_EVENT ||--o| ALERT : creates
  USER { uuid id PK string email UK enum role string password_hash }
  CAMERA { uuid id PK string code UK enum status float latitude float longitude string stream_endpoint_secret }
  WATCHLIST { uuid id PK string normalized_identifier enum severity bool active datetime valid_until }
  DETECTION_EVENT { uuid id PK string external_event_id UK string fingerprint UK uuid camera_id FK datetime occurred_at string normalized_vehicle_number json bounding_box }
  ALERT { uuid id PK uuid event_id FK uuid watchlist_id FK uuid camera_id FK enum status enum severity datetime acknowledged_at datetime resolved_at }
  AUDIT_LOG { int id PK uuid actor_id FK string action string resource_type json details datetime created_at }
```

Indexes support camera status/department/zone, plate/time, camera/time, active watchlist identifier, and alert status/time. Lists are bounded and relationship-heavy alert reads use joined loading.

## Adapter boundary

The prototype renderer consumes safe camera metadata and generates motion locally. Production adapters should expose capability metadata, health, a delivery reference, and normalized detections; secrets stay server-side. RTSP should terminate in an isolated media gateway producing HLS/WebRTC, never in the browser.

