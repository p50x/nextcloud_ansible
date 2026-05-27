#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r'''
---
module: occ_maintenance
short_description: Toggle Nextcloud maintenance mode via occ
version_added: "1.0.0"
description:
  - Idempotent module for enabling or disabling Nextcloud maintenance mode via C(occ).
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
  state:
    description:
      - Whether maintenance mode should be enabled or disabled.
    required: true
    type: str
    choices:
      - enabled
      - disabled
author:
  - Reiner Nippes
'''

EXAMPLES = r'''
- name: Turn maintenance mode on
  reinernippes.nextcloud.occ_maintenance:
    occ_path: /var/www/nextcloud/occ
    web_user: www-data
    state: enabled

- name: Turn maintenance mode off
  reinernippes.nextcloud.occ_maintenance:
    occ_path: /var/www/nextcloud/occ
    web_user: www-data
    state: disabled
'''

RETURN = r'''
planned_commands:
  description: Commands that would run in check mode or that were executed.
  returned: always
  type: list
current:
  description: Current maintenance state detected before the change.
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
    parse_json_output,
    run_occ,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            occ_path=dict(type="path", required=False),
            php_bin=dict(type="path", default="php"),
            web_user=dict(type="str"),
            chdir=dict(type="path"),
            state=dict(type="str", required=True, choices=["enabled", "disabled"]),
        ),
        supports_check_mode=True,
    )

    params = module.params
    apply_env_defaults(params, module)
    if not params.get("occ_path"):
        module.fail_json(msg="occ_path is required (set parameter or NEXTCLOUD_OCC_PATH env var)")

    state = params["state"]

    # Query current status
    run = run_occ(
        module,
        php_bin=params["php_bin"],
        occ_path=params["occ_path"],
        chdir=params.get("chdir"),
        argv=["status", "--output=json"],
        check_rc=True,
        web_user=params.get("web_user"),
    )
    payload = parse_json_output(run["stdout"])
    current = {
        "maintenance": bool((payload or {}).get("maintenance")),
        "installed": bool((payload or {}).get("installed")),
    }

    result = {
        "changed": False,
        "planned_commands": [],
        "current": current,
        "inspected_via": run["cmd"],
    }

    if state == "enabled":
        if current["maintenance"]:
            module.exit_json(**result)
        cmd = ["maintenance:mode", "--on"]
    else:
        if not current["maintenance"]:
            module.exit_json(**result)
        cmd = ["maintenance:mode", "--off"]

    result["planned_commands"] = [cmd]
    if module.check_mode:
        result["changed"] = True
        result["check_mode"] = True
        module.exit_json(**result)

    last_run = run_occ(
        module,
        php_bin=params["php_bin"],
        occ_path=params["occ_path"],
        chdir=params.get("chdir"),
        argv=cmd,
        check_rc=True,
        web_user=params.get("web_user"),
    )
    result.update(last_run)
    result["changed"] = True
    module.exit_json(**result)


if __name__ == "__main__":
    main()
