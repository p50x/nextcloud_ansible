#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r'''
---
module: occ_command
short_description: Run arbitrary Nextcloud occ commands
version_added: "1.0.0"
description:
  - Execute arbitrary Nextcloud C(occ) commands.
  - This is a thin wrapper intended for commands that are not covered by dedicated modules.
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
  command:
    description:
      - Raw C(occ) command string to execute.
    type: str
  argv:
    description:
      - Raw C(occ) argument vector to execute.
    type: list
    elements: str
  changed_when:
    description:
      - Changed flag to report.
    type: bool
    default: true
  expected_rcs:
    description:
      - Acceptable return codes.
    type: list
    elements: int
    default:
      - 0
author:
  - Reiner Nippes
'''

EXAMPLES = r'''
- name: Run a raw occ command without marking changed
  reinernippes.nextcloud.occ_command:
    occ_path: /var/www/nextcloud/occ
    command: status --output=json
    changed_when: false

- name: Run occ upgrade
  reinernippes.nextcloud.occ_command:
    occ_path: /var/www/nextcloud/occ
    web_user: www-data
    argv:
      - upgrade
      - --no-interaction
'''

RETURN = r'''
stdout:
  description: Raw stdout of the executed occ command.
  returned: always
  type: str
occ_rc:
  description: Return code of the occ command.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.reinernippes.nextcloud.plugins.module_utils.occ_common import (
    apply_env_defaults,
    run_occ,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            occ_path=dict(type="path", required=False),
            php_bin=dict(type="path", default="php"),
            web_user=dict(type="str"),
            chdir=dict(type="path"),
            command=dict(type="str"),
            argv=dict(type="list", elements="str"),
            changed_when=dict(type="bool", default=True),
            expected_rcs=dict(type="list", elements="int", default=[0]),
        ),
        mutually_exclusive=[("command", "argv")],
        supports_check_mode=True,
    )

    params = module.params
    apply_env_defaults(params, module)
    if not params.get("occ_path"):
        module.fail_json(msg="occ_path is required (set parameter or NEXTCLOUD_OCC_PATH env var)")

    if not params.get("command") and not params.get("argv"):
        module.fail_json(msg="either 'command' or 'argv' is required")

    result = {
        "changed": False,
        "planned_commands": [params.get("argv") or params.get("command")],
    }

    if module.check_mode:
        result["changed"] = bool(params["changed_when"])
        result["check_mode"] = True
        module.exit_json(**result)

    run = run_occ(
        module,
        php_bin=params["php_bin"],
        occ_path=params["occ_path"],
        chdir=params.get("chdir"),
        command=params.get("command"),
        argv=params.get("argv"),
        check_rc=False,
        web_user=params.get("web_user"),
    )
    if run["rc"] not in params["expected_rcs"]:
        module.fail_json(msg="occ command returned an unexpected rc", **run)
    result.update(run)
    result["occ_rc"] = run["rc"]
    if run["rc"] != 0:
        result["rc"] = 0
    result["changed"] = bool(params["changed_when"])
    module.exit_json(**result)


if __name__ == "__main__":
    main()
