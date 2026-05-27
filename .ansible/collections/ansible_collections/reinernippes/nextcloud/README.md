# `reinernippes.nextcloud` Ansible Collection

Idempotent Ansible modules for managing Nextcloud via the `occ` CLI.
Replaces raw `command: php occ …` calls with proper changed/failed handling.

## Installation

```bash
ansible-galaxy collection install reinernippes.nextcloud
```

Or via `requirements.yml`:

```yaml
collections:
  - name: reinernippes.nextcloud
```

Or from source:

```bash
cd reinernippes/nextcloud
ansible-galaxy collection build
ansible-galaxy collection install reinernippes-nextcloud-*.tar.gz
```

## Available Modules

| Module | Description |
|--------|-------------|
| `reinernippes.nextcloud.occ_app` | Install, enable, disable, remove Nextcloud apps |
| `reinernippes.nextcloud.occ_command` | Run arbitrary `occ` commands |
| `reinernippes.nextcloud.occ_config_app` | Get/set/delete app configuration values |
| `reinernippes.nextcloud.occ_config_system` | Get/set/delete system configuration values (`config.php`) |
| `reinernippes.nextcloud.occ_group` | Manage Nextcloud groups |
| `reinernippes.nextcloud.occ_info` | Query Nextcloud status and configuration (read-only) |
| `reinernippes.nextcloud.occ_maintenance` | Enable/disable maintenance mode |
| `reinernippes.nextcloud.occ_user` | Manage Nextcloud users |

## Common Parameters

All modules share these connection parameters:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `occ_path` | no | Path to the `occ` script. Falls back to `NEXTCLOUD_OCC_PATH` env var |
| `php_bin` | no | PHP binary to use (default: `php`). Falls back to `NEXTCLOUD_PHP_RUNTIME` env var |
| `web_user` | no | OS user to run occ as (via `sudo -u`). Falls back to `NEXTCLOUD_WEB_USER` env var |
| `chdir` | no | Working directory for the command |

You can set the environment variables once per play instead of repeating
the parameters on every task:

```yaml
- hosts: nextcloud
  environment:
    NEXTCLOUD_OCC_PATH: /var/www/nextcloud/occ
    NEXTCLOUD_WEB_USER: www-data
  tasks:
    - name: Enable an app
      reinernippes.nextcloud.occ_app:
        name: notify_push
        state: enabled
```

## Examples

### Manage apps

```yaml
- name: Ensure notify_push is enabled
  reinernippes.nextcloud.occ_app:
    name: notify_push
    state: enabled

- name: Disable an app
  reinernippes.nextcloud.occ_app:
    name: firstrunwizard
    state: disabled
```

### Set system config (simple)

```yaml
- name: Set overwrite.cli.url
  reinernippes.nextcloud.occ_config_system:
    key: overwrite.cli.url
    value: "https://cloud.example.com"
    state: present
```

### Set system config (nested with indices)

```yaml
- name: Set redis host
  reinernippes.nextcloud.occ_config_system:
    key: redis
    indices: host
    value: /var/run/redis/redis.sock
    state: present
```

### Set system config (array with loop)

```yaml
nextcloud_preview_providers:
  - 'OC\Preview\PNG'
  - 'OC\Preview\JPEG'
  - 'OC\Preview\GIF'

- name: Set preview providers
  reinernippes.nextcloud.occ_config_system:
    key: enabledPreviewProviders
    indices: "{{ idx }}"
    value: "{{ item }}"
    state: present
  loop: "{{ nextcloud_preview_providers }}"
  loop_control:
    index_var: idx
```

### JSON value_type (complex structures)

```yaml
- name: Set log.condition as JSON
  reinernippes.nextcloud.occ_config_system:
    key: log.condition
    value:
      apps:
        - admin_audit
    value_type: json
    state: present
```

### Set app config

```yaml
- name: Set admin_audit log file
  reinernippes.nextcloud.occ_config_app:
    app: admin_audit
    key: logfile
    value: /var/log/nextcloud/audit.log
    state: present
```

### Query info (read-only)

```yaml
- name: Get Nextcloud status
  reinernippes.nextcloud.occ_info:
    query: status
  register: nc_status
```

### Manage users

```yaml
- name: Create a user
  reinernippes.nextcloud.occ_user:
    name: johndoe
    password: "{{ user_password }}"
    groups:
      - staff

- name: Query user info
  reinernippes.nextcloud.occ_info:
    query: user
    name: johndoe
```

### Manage groups

```yaml
- name: List all groups
  reinernippes.nextcloud.occ_info:
    query: group
```

### Run arbitrary occ command

```yaml
- name: Run maintenance:repair
  reinernippes.nextcloud.occ_command:
    command: maintenance:repair
```

### Maintenance mode

```yaml
- name: Enable maintenance mode
  reinernippes.nextcloud.occ_maintenance:
    state: enabled
```

## Parameters Reference

### `indices`

Additional path components for nested system config.
Accepts a single value or a list.

| occ command | `key` | `indices` |
|-------------|-------|-----------|
| `config:system:set overwrite.cli.url` | `overwrite.cli.url` | *(empty)* |
| `config:system:set redis host` | `redis` | `host` |
| `config:system:set trusted_domains 0` | `trusted_domains` | `0` |
| `config:system:set log.condition apps 0` | `log.condition` | `[apps, "0"]` |

## Testing

```bash
cd tests
bash run_occ_module_tests.sh
```

The test playbook uses a `fake_occ.py` fixture that simulates the real
`occ` CLI, so no running Nextcloud instance is required.

## License

GPL-3.0-or-later
