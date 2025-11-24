# Ansible Documentation

Complete Ansible documentation has been moved to the centralized documentation directory.

## See Documentation

- **[Database Setup Guide](../docs/setup-database.md)** - Complete database setup with Ansible
- **[Troubleshooting Guide](../docs/troubleshooting.md)** - Common Ansible issues and solutions
- **[Documentation Index](../docs/README.md)** - All documentation

## Quick Links

### Setup
- [Ansible Setup Instructions](../docs/setup-database.md#method-1-ansible-setup-recommended)
- [Configure Inventory](../docs/setup-database.md#step-1-configure-inventory)
- [Set Passwords](../docs/setup-database.md#step-2-set-passwords)
- [Run Playbook](../docs/setup-database.md#step-3-run-playbook)

### Troubleshooting
- [Connection Refused Errors](../docs/troubleshooting.md#connection-refused)
- [Authentication Failed](../docs/troubleshooting.md#authentication-failed)
- [Ansible Connection Issues](../docs/troubleshooting.md#ansible-connection-issues)

## Running the Playbook

```bash
ansible-playbook -i inventory/production.yml --ask-vault-pass playbooks/march_database.yml
```

See [Database Setup Guide](../docs/setup-database.md) for complete instructions.