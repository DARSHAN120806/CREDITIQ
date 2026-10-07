# Deployment runbook

These files prepare deployment; no service has been deployed by this task.
Choose **one** host. Supabase remains the database on every option. Do not use local
PostgreSQL as a fallback. Keep RESEARCH_ONLY and release_ready=false.

## Shared prerequisites

1. Supply real API/frontend HTTPS domains, DNS, provider account, exact trusted reverse
   proxy IPs/CIDRs and a mounted Supabase CA certificate. Never set proxy trust to `*` or
   `/0`. On VPS/Compose with host Caddy, trust the actual peer address observed by Uvicorn
   (Docker bridge peer for Compose, loopback for host systemd). Provider ingress must
   overwrite forwarded headers; firewall the application port from other clients.
2. Copy production.env.example or staging.env.example into a private secrets store.
   Generate JWT with `python -c "import secrets; print(secrets.token_urlsafe(48))"` in
   your private terminal. Preserve a deployed signing key across routine image rollback.
   Do not mount operator credentials, .postgres, raw CSVs or database dumps into the API.
3. Run `python deploy/package_artifacts.py`. This creates ignored .deployment-assets.
   The Lite loader checks **all** artifact hashes, including saved research partition
   parquet files; these must remain private server-side. No raw CSVs or customer database
   dumps are copied. Metadata can contain historical local paths; images must be private.
4. From services/api, set PYTHONPATH to that directory and run:
   `python -m scripts.deployment_validation --env-file /private/staging.env --database --artifacts`.
   Run `--https` after deployment. A passing validator does not certify backups or alert delivery.
5. Build on Linux with Docker, scan the resulting images, and store immutable private tags:

```sh
docker build -f deploy/api.Dockerfile -t "$CREDITIQ_API_IMAGE" .
docker build -f deploy/web.Dockerfile --build-arg API_ORIGIN="$API_ORIGIN" -t "$CREDITIQ_WEB_IMAGE" .
docker push "$CREDITIQ_API_IMAGE"
docker push "$CREDITIQ_WEB_IMAGE"
```

Linux dependency installation/model loading must pass before release: existing artifact
runtime versions were validated on Windows. Do not silently upgrade them to make a build
pass. Verify both research dashboards in addition to a real Lite prediction.
Next rewrites are built with API_ORIGIN: use the **same** origin at build and runtime;
rebuild the web image when changing the backend domain.

## Railway

Create/link separate API and web services with private variables. Select
deploy/railway-api.json and deploy/railway-web.json as config paths for source builds.
For CLI upload, set RAILWAY_PROJECT_ID, RAILWAY_SERVICE_ID, RAILWAY_ENVIRONMENT and
RAILWAY_TOKEN privately, then run `python deploy/deploy.py railway api` (or web).
The adapter creates a clean .deployment-context and places the chosen config at its
root. It uploads **that context only**, including the generated artifact bundle.
Review/archive the context before a second upload; the script refuses overwrite.
Configure CA as a provider secret file/volume and API_ORIGIN as a web build variable.
Do not deploy directly from Git without supplying the ignored artifact bundle.

## Render

Use deploy/render.yaml as the Blueprint path. Create the creditiq-api-secrets environment
group first, including all fields in the selected env template; supply a secret CA file
and its actual mounted path. Set web API_ORIGIN at build and runtime.
Git builds lack ignored artifacts: use a private prebuilt image deployment or a private
build source containing the reviewed bundle. Configure the chosen image/tag in Render.
After provisioning, put its deploy-hook URL in RENDER_DEPLOY_HOOK and run
`python deploy/deploy.py render`. The hook contains a secret; never commit it.

## Coolify

Create two private Docker-image applications using the API/web images above. Set domains,
container ports 8000/3000, API health path /health/ready, environment values and CA mount.
Use Coolify's own TLS proxy; do not run a competing Caddy on ports 80/443.
For each application set COOLIFY_ORIGIN, COOLIFY_APPLICATION_UUID, COOLIFY_TOKEN privately,
then run `python deploy/deploy.py coolify`. This starts an already configured resource;
it does not guess ingress addresses or create secrets/domains.

## Docker Compose

Set CREDITIQ_API_IMAGE, CREDITIQ_WEB_IMAGE, CREDITIQ_RUNTIME_ENV_FILE, CREDITIQ_CA_FILE
and API_ORIGIN in the operator shell. `python deploy/deploy.py compose` validates the
Compose file, pulls images and starts the services. Runtime env is supplied to the API
only; web receives no database/JWT secrets. Ports bind to host loopback. Install Caddy
on the host using deploy/Caddyfile with FRONTEND_DOMAIN, API_DOMAIN and ACME_EMAIL.
The API container is non-root, read-only with a writable tmpfs and no Linux capabilities.
Treat the 2 GiB API memory limit as an initial value that must be load-tested.

## VPS systemd

Create a dedicated unprivileged creditiq OS user. Install the reviewed release under
/opt/creditiq/releases/<version> and atomically point /opt/creditiq/current to it. Create
the Python venv, install the locked requirements, copy the allowlisted artifact bundle
into its ml paths, and run npm ci/build with the deployed API_ORIGIN. Install the supplied
unit files; store secrets under /etc/creditiq with root ownership and restricted access.
Set the actual certificate path in runtime.env; put only API_ORIGIN in web.env.
Run `python deploy/deploy.py systemd api` and `... systemd web` as the service operator.
Install Caddy, open only 80/443 externally, and enable units after validation. No script
automatically installs packages, overwrites an existing release or opens firewall ports.

## Monitoring and restore gate

Use an **independent host/provider** for external monitoring; a timer on the application
host cannot detect that host disappearing. monitor.py checks HTTPS API readiness and
frontend login, sending a generic JSON alert on failure. Configure MONITOR_API_ORIGIN,
MONITOR_FRONTEND_ORIGIN, ALERT_WEBHOOK_URL privately. The systemd monitor unit/timer is
provided for a separate monitoring host. Configure provider deduplication/escalation;
this minimal monitor sends an alert each failed run. Test failure delivery before GO.

Confirm the Supabase plan's actual backup/PITR retention; do not assume availability.
With a **separate operator** PG service/password file, create an encrypted private backup:

```sh
pg_dump --dbname=service=creditiq_operator --format=custom --schema=public --file=/private/creditiq.dump
pg_restore --list /private/creditiq.dump
```

Record timestamp, checksum, row counts, revision and security inventory. Restore to an
empty isolated PostgreSQL target of a compatible version with required role identities
created first, then compare fingerprints and RLS/grants/policies. Never run restore
against the live target to test it. Use scripts/database_snapshot.py with the operator
connection for evidence; runtime intentionally cannot read alembic_version. A backup
file/listing alone does not prove restoration. No backup/restore was executed in this task.

## Release and rollback

Deploy staging first, perform authenticated HTTPS/browser tests, test alert delivery and
backup restoration, then promote the tested image/configuration. Keep old immutable images.
For failure, stop promotion/writes as appropriate and restore the previous compatible
image/config; preserve Supabase, restricted credentials, RLS and JWT key. Never roll back
to postgres credentials or a local database. Restore data only after pausing writers and
validating an isolated restore. No deployment script runs migrations or retraining.

References: [Railway CLI](https://docs.railway.com/cli/up),
[Render Blueprint](https://render.com/docs/blueprint-spec),
[Coolify application start](https://coolify.io/docs/api/endpoints/applications/start-application-by-uuid).
