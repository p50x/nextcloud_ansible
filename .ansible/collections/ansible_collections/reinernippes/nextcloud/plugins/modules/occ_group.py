#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r'''
---
module: occ_group
short_description: Manage Nextcloud groups via occ
version_added: "1.0.0"
description:
  - Idempotent module for creating and deleting Nextcloud groups via C(occ).
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
      - Falls back to C(NEXTCLOUD_PHP_RUNTIME) env var.
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
  name:
    description:
      - The group name.
    required: true
    type: str
  state:
    description:
      - Desired state of the group.
    type: str
    default: present
    choices:
      - present
      - absent
author:
  - Reiner Nippes
'''

EXAMPLES = r'''
- name: Ensure a group exists
  reinernippes.nextcloud.occ_group:
    occ_path: /var/www/nextcloud/occ
    web_user: www-data
    name: editors

- name: Delete a group
  reinernippes.nextcloud.occ_group:
    occ_path: /var/www/nextcloud/occ
    web_user: www-data
    name: editors
    state: absent
'''

RETURN = r'''
group:
  description: Current state of the group after the operation.
  returned: always
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.reinernippes.nextcloud.plugins.module_utils.occ_common import (
    apply_env_defaults,
    parse_json_output,
    run_occ,
)


def get_group_list(module, params):
    run = run_occ(
        module,
        php_bin=params["php_bin"],
        occ_path=params["occ_path"],
        chdir=params.get("chdir"),
        argv=["group:list", "--output=json"],
        check_rc=True,
        web_user=params.get("web_user"),
    )
    payload = parse_json_output(run["stdout"])
    if isinstance(payload, dict):
        return set(payload.keys())
    return set()


def occ_run(module, params, argv, check_rc=True):
    return run_occ(
        module,
        php_bin=params["php_bin"],
        occ_path=params["occ_path"],
        chdir=params.get("chdir"),
        argv=argv,
        check_rc=check_rc,
        web_user=params.get("web_user"),
    )


def main():
    module = AnsibleModule(
        argument_spec=dict(
            occ_path=dict(type="path", required=False),
            php_bin=dict(type="path", default="php"),
            web_user=dict(type="str"),
            chdir=dict(type="path"),
            name=dict(type="str", required=True),
            state=dict(type="str", default="present", choices=["present", "absent"]),
        ),
        supports_check_mode=True,
    )

    params = module.params
    apply_env_defaults(params, module)
    if not params.get("occ_path"):
        module.fail_json(msg="occ_path is required (set parameter or NEXTCLOUD_OCC_PATH env var)")

    name = params["name"]
    state = params["state"]

    existing_groups = get_group_list(module, params)
    group_exists = name in existing_groups

    result = {
        "changed": False,
        "group": {
            "name": name,
            "exists": group_exists,
        },
    }

    if state == "present":
        if group_exists:
            module.exit_json(**result)
        if module.check_mode:
            result["changed"] = True
            module.exit_json(**result)
        occ_run(module, params, ["group:add", name])
        result["changed"] = True
        result["group"]["exists"] = True
        module.exit_json(**result)

    if state == "absent":
        if not group_exists:
            module.exit_json(**result)
        if module.check_mode:
            result["changed"] = True
            module.exit_json(**result)
        occ_run(module, params, ["group:delete", name])
        result["changed"] = True
        result["group"]["exists"] = False
        module.exit_json(**result)


if __name__ == "__main__":
    main()
