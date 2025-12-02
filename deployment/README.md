# Deployment Configuration

This directory contains deployment configurations for the FitonDuty March Dashboard.

## Structure

```
deployment/
├── ansible/          # Ansible playbooks and roles
│   ├── playbooks/   # Deployment playbooks
│   ├── roles/       # Ansible roles
│   ├── inventory/   # Server inventories
│   └── vars/        # Variables and vaults
└── docker/          # Docker configuration
    └── Dockerfile   # Container build file
```

## Important: Migration Changes

**The repository structure has been reorganized.** If you're updating from the old structure, note these path changes:

### Dockerfile Location

**Old**: `./Dockerfile` (project root)
**New**: `deployment/docker/Dockerfile`

The Dockerfile path is **already updated** in Ansible playbooks:
```yaml
- name: Build container
  podman_image:
    name: fitonduty_dashboard_march
    path: /opt/fitonduty/fitonduty-dashboard-march
    build:
      file: deployment/docker/Dockerfile  # ← Updated
```

### Database Scripts

**Old paths**:
- `database/schema.sql`
- `database/create_schema.py`
- `database/seed_database.py`

**New paths**:
- `src/database/schema.sql`
- `src/database/management/create_schema.py`
- `src/database/management/seed_database.py`

These are **already updated** in the `march_database` role.

### Environment Files

**Old**: `.env`, `.env.production` (project root)
**New**: `config/environments/.env.development`, `.env.production`

The root `.env` is now a symlink to `config/environments/.env.development`.

**Ansible still creates**: `/opt/fitonduty/fitonduty-dashboard-march/.env` (this works correctly)

---

## Ansible Deployment

### Prerequisites

- Ansible installed on control machine
- SSH access to target servers
- Vault password file (`.vault_pass`) in ansible directory

### Deploy Dashboard

```bash
cd deployment/ansible

# Check connectivity
ansible-playbook -i inventory/production playbooks/connectivity.yml

# Deploy dashboard
ansible-playbook -i inventory/production playbooks/march_dashboard.yml
```

### Deploy Database

```bash
cd deployment/ansible

# Deploy database (schema only)
ansible-playbook -i inventory/production playbooks/march_database.yml \
  -e march_seed_mode=none

# Deploy database (with mock data - testing only)
ansible-playbook -i inventory/production playbooks/march_database.yml \
  -e march_seed_mode=mock
```

### Key Variables

Defined in `deployment/ansible/vars/production/vault.yml` (encrypted):
- `vault_postgres_password` - PostgreSQL admin password
- `vault_march_db_password` - March database user password
- `vault_secret_key` - Flask secret key

---

## Docker Build

### Local Build

From **project root**:

```bash
# Build
docker build -f deployment/docker/Dockerfile -t fitonduty-march .

# Run
docker run -p 8050:8050 \
  -e DATABASE_URL="postgresql://user:pass@host:5432/db" \
  fitonduty-march
```

**Important**: Build context is project root (`.`), Dockerfile is at `deployment/docker/Dockerfile`

### What the Dockerfile Does

1. Uses Python 3.12-slim base image
2. Installs system dependencies (libpq-dev, gcc)
3. Copies `pyproject.toml` and `uv.lock`
4. Installs Python dependencies via `uv`
5. Copies entire project (including `src/`, `config/`, etc.)
6. Runs with gunicorn: `app:app` (wrapper at root calls `src/app/main.py`)

---

## Ansible Roles

### `march_dashboard`

Deploys the dashboard application.

**Tasks**:
- Install podman and dependencies
- Clone repository
- Create `.env` file from template
- Build container image
- Create systemd service
- Start/restart service

**Path Changes Applied**:
- ✅ Dockerfile path updated to `deployment/docker/Dockerfile`

### `march_database`

Sets up the PostgreSQL database.

**Tasks**:
- Create database and user
- Copy schema and management scripts
- Run schema creation or seeding
- Configure pg_hba.conf

**Path Changes Applied**:
- ✅ Schema path: `src/database/schema.sql`
- ✅ Create script: `src/database/management/create_schema.py`
- ✅ Seed script: `src/database/management/seed_database.py`

---

## Troubleshooting

### Build Fails: "Dockerfile not found"

**Cause**: Old Ansible playbook trying to use `./Dockerfile`
**Fix**: Ensure you pulled the latest changes with updated Ansible tasks

### Schema File Not Found

**Cause**: Old path reference in Ansible
**Fix**: Update `march_database` role to use `src/database/schema.sql`

### Import Errors After Deployment

**Cause**: Application expects old structure
**Fix**: Ensure the entire repository is deployed, including `src/` directory

### Container Won't Start

Check logs:
```bash
# On server
journalctl -u fitonduty-dashboard-march -f

# Or podman logs
podman logs fitonduty_dashboard_march
```

Common issues:
- Missing `.env` file or wrong `DATABASE_URL`
- Database not accessible
- Port 8050 already in use

---

## Testing Deployment

### 1. Test Locally First

```bash
# Build and run locally
docker build -f deployment/docker/Dockerfile -t fitonduty-march .
docker run -p 8050:8050 --env-file .env fitonduty-march

# Access at http://localhost:8050
```

### 2. Test with Ansible (Staging)

```bash
cd deployment/ansible

# Deploy to staging/testing environment
ansible-playbook -i inventory/testing playbooks/march_dashboard.yml
```

### 3. Deploy to Production

Only after testing:
```bash
cd deployment/ansible
ansible-playbook -i inventory/production playbooks/march_dashboard.yml
```

---

## Rollback

If deployment fails:

1. **Revert to previous container**:
   ```bash
   # On server
   podman images  # Find previous image
   podman tag <old-image-id> fitonduty_dashboard_march:latest
   systemctl restart fitonduty-dashboard-march
   ```

2. **Redeploy previous git commit**:
   ```bash
   # On server
   cd /opt/fitonduty/fitonduty-dashboard-march
   git checkout <previous-commit>
   # Then rebuild container
   ```

3. **Full rollback via Ansible**:
   ```bash
   # Update inventory to point to previous commit
   # Re-run playbook
   ```

---

## Notes for CI/CD

If you have CI/CD pipelines, update:

1. **Docker build command**:
   ```yaml
   # Old
   docker build -t app .

   # New
   docker build -f deployment/docker/Dockerfile -t app .
   ```

2. **File paths in tests/scripts**:
   - Use `src/` imports
   - Reference `deployment/` for Docker files
   - Config files in `config/environments/`

3. **Database migrations**:
   - Scripts in `src/database/management/`
   - Schema in `src/database/schema.sql`

---

## See Also

- **Main README**: `../README.md`
- **Migration Guide**: `../MIGRATION_COMPLETE.md`
- **Ansible README**: `ansible/README.md`
- **Scripts Documentation**: `../scripts/README.md`
