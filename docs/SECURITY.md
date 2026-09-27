# Security

- Passwords use Argon2 through `pwdlib`; JWTs are signed with an environment-held secret and expire.
- Admin mutation endpoints enforce role checks in FastAPI. Operators can monitor, search, acknowledge, and resolve.
- Pydantic validates event fields, coordinates, confidence and bounding boxes; SQLAlchemy parameterizes queries.
- Camera connection material is excluded from frontend schemas. Production stores only a vault/KMS secret reference.
- Login and security-sensitive mutations create audit records. Audit logs should become append-only/WORM downstream.
- CORS is allowlisted. Keep Swagger private or authenticated in production.
- Local demo traffic is HTTP. Production TLS/WSS terminates at a managed ingress; use mTLS for camera/edge-to-ingest paths.
- Put cameras in untrusted device VLANs, media gateways in an ingest zone, APIs in private application subnets, databases/caches in data subnets, and operator clients behind identity-aware access. Deny lateral movement by default.
- Login and ingestion have local IP-based rate limits through SlowAPI. Add gateway and Redis-backed per-identity limits for multi-replica production deployments.
- Rotate signing/database credentials, use managed secrets, scan images/dependencies, pin production digests, generate an SBOM, and sign releases.
- Encrypt disks, database, backups and object storage; minimize plate retention and access; define lawful-purpose controls and deletion holds.
- Revoke seeded accounts and set `DEMO_MODE=false` outside demos. Never expose raw RTSP credentials to clients.

Threats considered include credential stuffing, malicious/malformed inference, replay/duplicate events, broken object authorization, camera compromise, feed exfiltration, alert tampering, and audit deletion. Remaining prototype gaps are documented in the README.

