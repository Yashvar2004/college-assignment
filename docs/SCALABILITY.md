# Scaling toward 80,000 cameras

## Assumptions and capacity envelope

Illustrative assumptions: 80,000 cameras; 1080p H.265 average 2 Mb/s; 10% concurrently viewed centrally; one metadata event per camera per 10 seconds at peak; 1.5 KB normalized event; 30-day searchable metadata. Prices vary by provider, region, discounts, date, retention and egress—figures below are planning ranges, not quotes.

- Sending every primary stream centrally would be **160 Gb/s** (80,000 × 2 Mb/s), about **1.73 PB/day** before replicas. That is deliberately avoided.
- A 10% viewing/analytics subset is ~16 Gb/s. Prefer substreams (200–500 Kb/s), adaptive bitrate, operator-on-demand sessions, edge recording, and event clips.
- Peak event input at one per 10 seconds is 8,000 events/s and ~12 MB/s raw payload, then multiplied by replication/index overhead. Design for 3× bursts.

## Deployment topology

Run camera protocol handling, buffering, lightweight motion/ANPR and local hot retention at district/edge clusters. Regional clusters terminate streams, manage device partitions, perform GPU inference and retain warm video. Central services receive metadata, thumbnails/event clips and on-demand proxy sessions. Cameras are consistently assigned by department/region/camera ID so ownership and failover are predictable.

Stateless API/ingestion/WebSocket services scale horizontally behind L7 load balancers. Separate control APIs from high-volume ingest. Use autoscaling on queue lag, events/s, active sockets and CPU. A connection gateway maintains WebSockets; pub/sub fans updates to the owning node.

## Messaging and data

Use Kafka for durable ordered event streams with topics partitioned by `camera_id` (detections, health, commands, audit). Consumer groups handle validation, enrichment, watchlist matching and notification. Redis serves ephemeral presence, hot camera state, distributed rate limits and WebSocket fan-out; RabbitMQ is suitable for command/task queues but not the long-retained analytics backbone.

PostgreSQL stores control-plane records. Partition detections/alerts by month and optionally region; retain focused B-tree/BRIN indexes, use PgBouncer, read replicas for search/reporting, and archive old partitions. A dedicated search store can support fuzzy investigations. Cache camera metadata and active watchlist snapshots; invalidate via change events. Tenant/department IDs become mandatory keys and partition/RLS dimensions.

## Compute and accelerators

GPU placement follows bandwidth economics: inference near cameras. Benchmark the actual model; as a planning example, if one GPU sustains 80 sampled 5-FPS streams, 80,000 continuous streams require ~1,000 GPUs before N+1 capacity. Motion gating, lower FPS, batching, INT8 and specialist NPUs can reduce this materially. Do not procure from an unbenchmarked estimate.

## Storage and retention

- **Hot:** edge NVMe, 24–72 hours, rapid playback and circular overwrite.
- **Warm:** regional object storage, event clips and selected streams for 7–30 days.
- **Cold:** lifecycle to archive object tiers for policy/legal holds, typically 90–365 days.

At 2 Mb/s, one camera produces ~21.6 GB/day; all streams produce ~1.73 PB/day. Therefore store primary video at edge, centrally retain event clips, deduplicate, use H.265, and apply policy per department/classification. Metadata at the stated peak is roughly 1.0 TB/day raw (8,000 × 1.5 KB × 86,400), requiring compression, lifecycle partitions and aggregation. Replicate object manifests; use immutable retention where evidence rules require it.

## Reliability and operations

Deploy across three availability zones per region with N+1 edge nodes, replicated Kafka, multi-AZ PostgreSQL, cache failover and health-aware load balancing. Define RPO ≤5 minutes for control/alert data and RTO ≤30 minutes centrally; edge buffers tolerate WAN loss. Use PITR, cross-region encrypted backups, quarterly restore tests, infrastructure-as-code and documented regional failover.

Prometheus-compatible metrics cover camera availability, frame age, ingest rejection/dedup, match latency, queue lag, alert delivery and DB health. Centralize structured logs, OpenTelemetry traces and immutable audit export. Synthetic cameras continuously test end-to-end SLOs.

Apply zero trust, device certificates, signed firmware, secure boot where available, segmented camera VLANs, egress allowlists, mTLS, short-lived operator identity, least privilege, SIEM/SOC response, vulnerability management and regular red-team exercises. Multi-department tenancy requires scoped identities, tenant keys on every row/event, RLS, encryption-key separation, delegated administration, quotas and cross-tenant audit tests.

## Approximate costs

Prototype: one small API/web host, managed PostgreSQL/Redis or a single Docker host, and modest object storage: roughly **US$75–300/month**, excluding staff and video egress.

At scale, edge hardware/network dominates. A rough order-of-magnitude range is **US$1–5+ million/month** for regional compute/GPU, databases, messaging, observability, support and retained event media, plus one-time edge/camera/network procurement potentially in the tens of millions. Full central retention of 1.73 PB/day would be economically dominant and is not assumed. Build a bill of materials from measured bitrate, inference FPS, concurrency, retention, redundancy, egress and local procurement; cloud pricing changes by region/provider/date.

