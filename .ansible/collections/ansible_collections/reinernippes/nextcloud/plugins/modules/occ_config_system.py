#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r'''
---
module: occ_config_system
short_description: Manage Nextcloud system config via occ
version_added: "1.0.0"
description:
  - Idempotent module for setting and deleting Nextcloud system configuration values via C(occ).
  - Parameters C(occ_path), C(php_bin), and C(web_user) fall back to the
    environment variables C(NEXTCLOUD_OCC_PATH), C(NEXTCLOUD_PHP_RUNTIME),
    and C(NEXTCLOUD_WEB_USER) respectively.
options:
  occ_path:
    description:
      - Path to the Nextcloud C(occ) script.
      - Falls back to C(NEXTCLOUD_OCC_PATH) env var.
    type: path
  php_bin:
    description:
      - PHP binary used to execute C(occ).
    type: path
    default: php
  web_user:
    description:
      - OS user that runs the web server.
      - When set, occ is executed via C(sudo -u <web_user>).
      - Falls back to C(NEXTCLOUD_WEB_USER) env var.
    type: str
  chdir:
    description:
      - Working directory for the command.
    type: path
  key:
    description:
      - System config key to set or delete.
    required: true
    type: str
  indices:
    description:
      - Additional path components (sub-keys / array indices) for hierarchical config.
      - Accepts a single value or a list.
    type: raw
  value:
    description:
      - Desired value. Required when C(state=present) unless C(value_type=null).
    type: raw
  value_type:
    description:
      - Nextcloud config type to pass to C(config:system:set).
    type: str
    default: string
    choices:
      - string
      - boolean
      - integer
      - float
      - json
      - null
  state:
    description:
      - Whether the key should be present or absent.
    type: str
    required: true
    choices:
      - present
      - absent
  update_only:
    description:
      - Pass C(--update-only) — only update existing keys.
    type: bool
    default: false
  create_only:
    description:
      - Only set the value if the key does not already exist.
    type: bool
    default: false
  sensitive:
    description:
      - Mark a config value as sensitive when supported.
    type: bool
  lazy:
    description:
      - Mark a config value as lazy when supported.
    type: bool
author:
  - Reiner Nippes
'''

EXAMPLES = r'''
- name: Set overwrite.cli.url
  reinernippes.nextcloud.occ_config_system:
    occ_path: /var/www/nextcloud/occ
    web_user: www-data
    key: overwrite.cli.url
    value: https://cloud.example.test
    state: present

- name: Set a hierarchical config value
  reinernippes.nextcloud.occ_config_system:
    occ_path: /var/www/nextcloud/occ
    key: log.condition
    indices: [apps, 0]
    value: admin_audit
    state: present

- name: Delete a system config key
  reinernippes.nextcloud.occ_config_system:
    occ_path: /var/www/nextcloud/occ
    key: maintenance_window_start
    state: absent
'''

RETURN = r'''
planned_commands:
  description: Commands that would run in check mode or that were executed.
  returned: always
  type: list
current:
  description: Current config state detected before the change.
  returned: always
  type: dict
stdout:
  description: Raw stdout of the last executed occ command.
  returned: when a command is executed
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.reinernippes.nextcloud.plugins.module_utils.occ_common import (
    apply_env_defaults,
    config_value_from_output,
    format_cli_value,
    looks_like_missing_value,
    normalize_indices,
    run_occ,
    values_equal,
)


def get_config_state(module, params):
    key = str(params["key"])
    idx = normalize_indices(params.get("indices"))
    value_type = params.get("value_type", "string")

    argv = ["config:system:get", key] + idx
    if value_type == "json":
        argv.append("--output=json")

    run = run_occ(
        module,
        php_bin=params["php_bin"],
        occ_path=params["occ_path"],
        chdir=params.get("chdir"),
        argv=argv,
        check_rc=False,
        web_user=params.get("web_user"),
    )

    if run["rc"] == 0:
        return {"exists": True, "value": config_value_from_output(run["stdout"])}, run
    if looks_like_missing_value(run):
        return {"exists": False, "value": None}, run
    module.fail_json(msg="failed to query current Nextcloud config", **run)


def apply_or_plan(module, params, result, commands):
    result["planned_commands"] = commands
    if module.check_mode:
        result["changed"] = True
        result["check_mode"] = True
        module.exit_json(**result)

    last_run = None
    for argv in commands:
        last_run = run_occ(
            module,
            php_bin=params["php_bin"],
            occ_path=params["occ_path"],
            chdir=params.get("chdir"),
            argv=argv,
            check_rc=True,
            web_user=params.get("web_user"),
        )
    if last_run:
        result.update(last_run)
    result["changed"] = True
    module.exit_json(**result)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            occ_path=dict(type="path", required=False),
            php_bin=dict(type="path", default="php"),
            web_user=dict(type="str"),
            chdir=dict(type="path"),
            key=dict(type="str", required=True),
            indices=dict(type="raw"),
            value=dict(type="raw"),
            value_type=dict(type="str", default="string", choices=["string", "boolean", "integer", "float", "json", "null"]),
            state=dict(type="str", required=True, choices=["present", "absent"]),
            update_only=dict(type="bool", default=False),
            create_only=dict(type="bool", default=False),
            sensitive=dict(type="bool"),
            lazy=dict(type="bool"),
        ),
        supports_check_mode=True,
    )

    params = module.params
    apply_env_defaults(params, module)
    if not params.get("occ_path"):
        module.fail_json(msg="occ_path is required (set parameter or NEXTCLOUD_OCC_PATH env var)")

    state = params["state"]

    # Auto-detect json value_type when value is a list or dict
    if state == "present":
        value = params.get("value")
        if isinstance(value, (list, dict)) and params["value_type"] == "string":
            params["value_type"] = "json"
        if params.get("value") is None and params.get("value_type") != "null":
            module.fail_json(msg="parameter 'value' is required when state=present")

    current, inspect_run = get_config_state(module, params)
    result = {
        "changed": False,
        "planned_commands": [],
        "current": current,
        "inspected_via": inspect_run["cmd"],
    }

    if state == "absent":
        if not current["exists"]:
            module.exit_json(**result)
        idx = normalize_indices(params.get("indices"))
        cmd = ["config:system:delete", str(params["key"])] + idx
        apply_or_plan(module, params, result, [cmd])

    # state == present
    if current["exists"] and values_equal(inspect_run["stdout"], params.get("value"), params["value_type"]):
        module.exit_json(**result)

    if params["create_only"] and current["exists"]:
        module.exit_json(**result)

    idx = normalize_indices(params.get("indices"))
    cmd = ["config:system:set", str(params["key"])] + idx
    cmd.append("--value=%s" % format_cli_value(params.get("value"), params["value_type"]))
    if params["value_type"]:
        cmd.append("--type=%s" % params["value_type"])
    if params["update_only"]:
        cmd.append("--update-only")
    if params.get("sensitive") is not None:
        cmd.append("--sensitive" if params["sensitive"] else "--no-sensitive")
    if params.get("lazy") is not None:
        cmd.append("--lazy" if params["lazy"] else "--no-lazy")

    apply_or_plan(module, params, result, [cmd])


if __name__ == "__main__":
    main()
