#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r'''
---
module: occ_info
short_description: Read Nextcloud information via occ
version_added: "1.0.0"
description:
  - Executes read-only Nextcloud C(occ) commands and returns parsed facts.
  - Useful for querying server status, app state, config values, users, and groups.
  - Parameters C(occ_path), C(php_bin), and C(web_user) fall back to the
    environment variables C(NEXTCLOUD_OCC_PATH), C(NEXTCLOUD_PHP_RUNTIME),
    and C(NEXTCLOUD_WEB_USER) respectively.
options:
  occ_path:
    description:
      - Path to the Nextcloud C(occ) script on the target host.
      - Falls back to C(NEXTCLOUD_OCC_PATH) env var.
    type: path
  php_bin:
    description:
      - PHP binary used to execute C(occ).
    type: path
    default: php
  web_user:
    description:
      - OS user that runs the web server (e.g. C(www-data), C(apache), C(wwwrun)).
      - When set, occ is executed via C(sudo -u <web_user>).
      - Falls back to C(NEXTCLOUD_WEB_USER) env var.
    type: str
  chdir:
    description:
      - Working directory in which the command should run.
      - Defaults to the parent directory of C(occ_path).
    type: path
  query:
    description:
      - Read operation to perform.
    required: true
    type: str
    choices:
      - status
      - app
      - app_list
      - config_system
      - config_app
      - user
      - user_list
      - group
      - raw
  name:
    description:
      - App name when C(query=app), user ID when C(query=user),
        or group name when C(query=group) (to list members).
    type: str
  app:
    description:
      - App name when C(query=config_app).
    type: str
  key:
    description:
      - Config key for C(config_system) or C(config_app).
    type: str
  indices:
    description:
      - Additional path components (sub-keys / array indices) for hierarchical
        system config.
      - Accepts a single value or a list.
    type: raw
  command:
    description:
      - Raw C(occ) command string to execute when C(query=raw).
    type: str
  argv:
    description:
      - Raw C(occ) argument vector to execute when C(query=raw).
    type: list
    elements: str
author:
  - Reiner Nippes
'''

EXAMPLES = r'''
- name: Read Nextcloud status
  reinernippes.nextcloud.occ_info:
    occ_path: /var/www/nextcloud/occ
    query: status

- name: Check whether notify_push is enabled
  reinernippes.nextcloud.occ_info:
    occ_path: /var/www/nextcloud/occ
    query: app
    name: notify_push

- name: Read overwrite.cli.url
  reinernippes.nextcloud.occ_info:
    occ_path: /var/www/nextcloud/occ
    query: config_system
    key: overwrite.cli.url

- name: Read OnlyOffice app config
  reinernippes.nextcloud.occ_info:
    occ_path: /var/www/nextcloud/occ
    query: config_app
    app: onlyoffice
    key: DocumentServerUrl

- name: Get user info
  reinernippes.nextcloud.occ_info:
    occ_path: /var/www/nextcloud/occ
    query: user
    name: johndoe

- name: List all users
  reinernippes.nextcloud.occ_info:
    occ_path: /var/www/nextcloud/occ
    query: user_list

- name: List all groups
  reinernippes.nextcloud.occ_info:
    occ_path: /var/www/nextcloud/occ
    query: group

- name: List members of a group
  reinernippes.nextcloud.occ_info:
    occ_path: /var/www/nextcloud/occ
    query: group
    name: editors
'''

RETURN = r'''
status:
  description: Parsed output of C(occ status --output=json).
  returned: when query=status
  type: dict
apps:
  description: Enabled and disabled app names.
  returned: when query=app_list
  type: dict
app_state:
  description: State flags for a single app.
  returned: when query=app
  type: dict
value:
  description: Retrieved config value.
  returned: when query=config_system or query=config_app and the key exists
  type: raw
exists:
  description: Whether the requested config value exists.
  returned: when query=config_system or query=config_app
  type: bool
user_info:
  description: User information dict from C(user:info --output=json).
  returned: when query=user
  type: dict
user_exists:
  description: Whether the queried user exists.
  returned: when query=user
  type: bool
users:
  description: Dict of users from C(user:list --output=json).
  returned: when query=user_list
  type: dict
groups:
  description: Dict or list of groups/members.
  returned: when query=group
  type: raw
stdout:
  description: Raw stdout of the executed occ command.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.reinernippes.nextcloud.plugins.module_utils.occ_common import (
    apply_env_defaults,
    config_value_from_output,
    extract_app_sets,
    looks_like_missing_value,
    normalize_indices,
    parse_json_output,
    run_occ,
)


def fail_missing(module, param_name, query):
    module.fail_json(msg="parameter '%s' is required when query=%s" % (param_name, query))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            occ_path=dict(type="path", required=False),
            php_bin=dict(type="path", default="php"),
            web_user=dict(type="str"),
            chdir=dict(type="path"),
            query=dict(type="str", required=True, choices=[
                "status", "app", "app_list", "config_system", "config_app",
                "user", "user_list", "group", "raw",
            ]),
            name=dict(type="str"),
            app=dict(type="str"),
            key=dict(type="str"),
            indices=dict(type="raw"),
            command=dict(type="str"),
            argv=dict(type="list", elements="str"),
        ),
        mutually_exclusive=[("command", "argv")],
        supports_check_mode=True,
    )

    params = module.params
    apply_env_defaults(params, module)
    if not params.get("occ_path"):
        module.fail_json(msg="occ_path is required (set parameter or NEXTCLOUD_OCC_PATH env var)")
    query = params["query"]
    occ_path = params["occ_path"]
    php_bin = params["php_bin"]
    chdir = params["chdir"]
    web_user = params.get("web_user")

    result = {
        "changed": False,
        "query": query,
    }

    if query == "status":
        run = run_occ(module, php_bin=php_bin, occ_path=occ_path, chdir=chdir, argv=["status", "--output=json"], check_rc=True, web_user=web_user)
        payload = parse_json_output(run["stdout"])
        result.update(run)
        result["status"] = payload
        result["installed"] = bool((payload or {}).get("installed"))
        result["maintenance"] = bool((payload or {}).get("maintenance"))
        module.exit_json(**result)

    if query == "app_list":
        run = run_occ(module, php_bin=php_bin, occ_path=occ_path, chdir=chdir, argv=["app:list", "--output=json"], check_rc=True, web_user=web_user)
        payload = parse_json_output(run["stdout"])
        enabled, disabled = extract_app_sets(payload)
        result.update(run)
        result["apps"] = {
            "enabled": sorted(enabled),
            "disabled": sorted(disabled),
        }
        module.exit_json(**result)

    if query == "app":
        name = params.get("name")
        if not name:
            fail_missing(module, "name", query)
        run = run_occ(module, php_bin=php_bin, occ_path=occ_path, chdir=chdir, argv=["app:list", "--output=json"], check_rc=True, web_user=web_user)
        payload = parse_json_output(run["stdout"])
        enabled, disabled = extract_app_sets(payload)
        app_state = {
            "name": name,
            "installed": name in enabled or name in disabled,
            "enabled": name in enabled,
            "disabled": name in disabled,
        }
        result.update(run)
        result["app_state"] = app_state
        module.exit_json(**result)

    if query in ("config_system", "config_app"):
        key = params.get("key")
        idx = normalize_indices(params.get("indices"))
        if not key:
            fail_missing(module, "key", query)

        if query == "config_system":
            argv = ["config:system:get", str(key)] + idx
        else:
            app = params.get("app")
            if not app:
                fail_missing(module, "app", query)
            argv = ["config:app:get", str(app), str(key)]

        run = run_occ(module, php_bin=php_bin, occ_path=occ_path, chdir=chdir, argv=argv, check_rc=False, web_user=web_user)
        result.update(run)
        if run["rc"] == 0:
            result["occ_rc"] = run["rc"]
            result["exists"] = True
            result["value"] = config_value_from_output(run["stdout"])
            module.exit_json(**result)

        if looks_like_missing_value(run):
            result["occ_rc"] = run["rc"]
            result["rc"] = 0
            result["exists"] = False
            result["value"] = None
            module.exit_json(**result)

        module.fail_json(msg="occ info query failed", **result)

    if query == "user":
        name = params.get("name")
        if not name:
            fail_missing(module, "name", query)
        run = run_occ(module, php_bin=php_bin, occ_path=occ_path, chdir=chdir, argv=["user:info", name, "--output=json"], check_rc=False, web_user=web_user)
        result.update(run)
        if run["rc"] == 0:
            info = parse_json_output(run["stdout"])
            result["user_info"] = info
            result["user_exists"] = True
        else:
            result["user_info"] = None
            result["user_exists"] = False
            result["occ_rc"] = run["rc"]
            result["rc"] = 0
        module.exit_json(**result)

    if query == "user_list":
        run = run_occ(module, php_bin=php_bin, occ_path=occ_path, chdir=chdir, argv=["user:list", "--output=json"], check_rc=True, web_user=web_user)
        result.update(run)
        result["users"] = parse_json_output(run["stdout"]) or {}
        module.exit_json(**result)

    if query == "group":
        name = params.get("name")
        if name:
            # List members of a specific group
            run = run_occ(module, php_bin=php_bin, occ_path=occ_path, chdir=chdir, argv=["group:list", "--output=json"], check_rc=True, web_user=web_user)
            payload = parse_json_output(run["stdout"]) or {}
            result.update(run)
            if name in payload:
                result["groups"] = {name: payload[name]}
                result["group_exists"] = True
                result["members"] = payload[name]
            else:
                result["groups"] = {}
                result["group_exists"] = False
                result["members"] = []
        else:
            # List all groups
            run = run_occ(module, php_bin=php_bin, occ_path=occ_path, chdir=chdir, argv=["group:list", "--output=json"], check_rc=True, web_user=web_user)
            payload = parse_json_output(run["stdout"]) or {}
            result.update(run)
            result["groups"] = payload
        module.exit_json(**result)

    # query == "raw"
    command = params.get("command")
    argv = params.get("argv")
    if not command and not argv:
        module.fail_json(msg="either 'command' or 'argv' is required when query=raw")

    run = run_occ(module, php_bin=php_bin, occ_path=occ_path, chdir=chdir, command=command, argv=argv, check_rc=True, web_user=web_user)
    result.update(run)
    try:
        result["json"] = parse_json_output(run["stdout"])
    except Exception:
        pass
    module.exit_json(**result)


if __name__ == "__main__":
    main()
