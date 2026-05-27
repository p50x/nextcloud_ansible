#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r'''
---
module: occ_app
short_description: Manage Nextcloud apps via occ
version_added: "1.0.0"
description:
  - Idempotent module for installing, enabling, disabling, and removing Nextcloud apps via C(occ).
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
  name:
    description:
      - App name to manage.
    required: true
    type: str
  state:
    description:
      - Desired state of the app.
    required: true
    type: str
    choices:
      - present
      - absent
      - installed
      - enabled
      - disabled
  force:
    description:
      - Pass C(--force) for app installation or enablement.
    type: bool
    default: false
  keep_disabled:
    description:
      - Pass C(--keep-disabled) during app installation.
    type: bool
    default: false
author:
  - Reiner Nippes
'''

EXAMPLES = r'''
- name: Enable notify_push
  reinernippes.nextcloud.occ_app:
    occ_path: /var/www/nextcloud/occ
    web_user: www-data
    name: notify_push
    state: enabled

- name: Install an app but keep it disabled
  reinernippes.nextcloud.occ_app:
    occ_path: /var/www/nextcloud/occ
    name: contacts
    state: installed
    keep_disabled: true

- name: Remove an app
  reinernippes.nextcloud.occ_app:
    occ_path: /var/www/nextcloud/occ
    name: firstrunwizard
    state: absent
'''

RETURN = r'''
planned_commands:
  description: Commands that would run in check mode or that were executed.
  returned: always
  type: list
current:
  description: Current app state detected before the change.
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
    extract_app_sets,
    parse_json_output,
    run_occ,
)


def get_app_state(module, params):
    run = run_occ(
        module,
        php_bin=params["php_bin"],
        occ_path=params["occ_path"],
        chdir=params.get("chdir"),
        argv=["app:list", "--output=json"],
        check_rc=True,
        web_user=params.get("web_user"),
    )
    payload = parse_json_output(run["stdout"])
    enabled, disabled = extract_app_sets(payload)
    name = params["name"]
    state = {
        "name": name,
        "installed": name in enabled or name in disabled,
        "enabled": name in enabled,
        "disabled": name in disabled,
    }
    return state, run


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
            name=dict(type="str", required=True),
            state=dict(type="str", required=True, choices=["present", "absent", "installed", "enabled", "disabled"]),
            force=dict(type="bool", default=False),
            keep_disabled=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    params = module.params
    apply_env_defaults(params, module)
    if not params.get("occ_path"):
        module.fail_json(msg="occ_path is required (set parameter or NEXTCLOUD_OCC_PATH env var)")

    state = params["state"]
    name = params["name"]
    force = params["force"]
    keep_disabled = params["keep_disabled"]

    current, inspect_run = get_app_state(module, params)
    result = {
        "changed": False,
        "planned_commands": [],
        "current": current,
        "inspected_via": inspect_run["cmd"],
    }

    if state in ("present", "installed"):
        if current["installed"]:
            module.exit_json(**result)
        cmd = ["app:install"]
        if force:
            cmd.append("--force")
        if keep_disabled:
            cmd.append("--keep-disabled")
        cmd.append(name)
        apply_or_plan(module, params, result, [cmd])

    if state == "enabled":
        if current["enabled"]:
            module.exit_json(**result)
        commands = []
        if not current["installed"]:
            install_cmd = ["app:install"]
            if force:
                install_cmd.append("--force")
            install_cmd.append(name)
            commands.append(install_cmd)
        commands.append(["app:enable"] + (["--force"] if force else []) + [name])
        apply_or_plan(module, params, result, commands)

    if state == "disabled":
        if not current["installed"] or current["disabled"]:
            module.exit_json(**result)
        apply_or_plan(module, params, result, [["app:disable", name]])

    if state == "absent":
        if not current["installed"]:
            module.exit_json(**result)
        apply_or_plan(module, params, result, [["app:remove", name]])


if __name__ == "__main__":
    main()
