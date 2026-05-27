#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r'''
---
module: occ_user
short_description: Manage Nextcloud users via occ
version_added: "1.0.0"
description:
  - Idempotent module for creating, deleting, enabling, and disabling Nextcloud users via C(occ).
  - Supports setting display name, email, quota, group membership, and arbitrary user settings.
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
      - The user ID (login name).
    required: true
    type: str
  state:
    description:
      - Desired state of the user.
    type: str
    default: present
    choices:
      - present
      - absent
      - enabled
      - disabled
  password:
    description:
      - Password for user creation. Required when creating a new user.
    type: str
    no_log: true
  display_name:
    description:
      - Display name for the user. Set only on creation or when changed.
    type: str
  email:
    description:
      - Email address for the user.
    type: str
  quota:
    description:
      - Storage quota for the user (e.g. C(1 GB), C(500 MB), C(none), C(default)).
    type: str
  groups:
    description:
      - List of groups the user should belong to.
      - Groups not in this list will be removed from the user unless C(append_groups=true).
      - Groups that do not exist will be created automatically.
      - Only evaluated when C(state=present) or C(state=enabled).
    type: list
    elements: str
  append_groups:
    description:
      - If C(true), add the listed groups without removing existing memberships.
      - If C(false) (default), enforce exact group membership.
    type: bool
    default: false
  settings:
    description:
      - Dict of arbitrary user settings to apply via C(user:setting).
      - Keys are in the format C(app key) e.g. C(core lang), C(settings email).
    type: dict
author:
  - Reiner Nippes
'''

EXAMPLES = r'''
- name: Create a user with groups
  reinernippes.nextcloud.occ_user:
    occ_path: /var/www/nextcloud/occ
    web_user: www-data
    name: johndoe
    password: "{{ user_password }}"
    display_name: "John Doe"
    email: john@example.com
    quota: "5 GB"
    groups:
      - staff
      - editors

- name: Disable a user
  reinernippes.nextcloud.occ_user:
    occ_path: /var/www/nextcloud/occ
    web_user: www-data
    name: johndoe
    state: disabled

- name: Delete a user
  reinernippes.nextcloud.occ_user:
    occ_path: /var/www/nextcloud/occ
    web_user: www-data
    name: johndoe
    state: absent
'''

RETURN = r'''
user:
  description: Current state of the user after the operation.
  returned: always
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.reinernippes.nextcloud.plugins.module_utils.occ_common import (
    apply_env_defaults,
    parse_json_output,
    run_occ,
)


def get_user_info(module, params, user_id):
    run = run_occ(
        module,
        php_bin=params["php_bin"],
        occ_path=params["occ_path"],
        chdir=params.get("chdir"),
        argv=["user:info", user_id, "--output=json"],
        check_rc=False,
        web_user=params.get("web_user"),
    )
    if run["rc"] != 0:
        return None
    return parse_json_output(run["stdout"])


def get_user_groups(module, params, user_id):
    run = run_occ(
        module,
        php_bin=params["php_bin"],
        occ_path=params["occ_path"],
        chdir=params.get("chdir"),
        argv=["user:info", user_id, "--output=json"],
        check_rc=False,
        web_user=params.get("web_user"),
    )
    if run["rc"] != 0:
        return []
    info = parse_json_output(run["stdout"])
    if info and "groups" in info:
        return list(info["groups"])
    return []


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


def occ_run(module, params, argv, check_rc=True, environ_update=None):
    return run_occ(
        module,
        php_bin=params["php_bin"],
        occ_path=params["occ_path"],
        chdir=params.get("chdir"),
        argv=argv,
        check_rc=check_rc,
        web_user=params.get("web_user"),
        environ_update=environ_update,
    )


def main():
    module = AnsibleModule(
        argument_spec=dict(
            occ_path=dict(type="path", required=False),
            php_bin=dict(type="path", default="php"),
            web_user=dict(type="str"),
            chdir=dict(type="path"),
            name=dict(type="str", required=True),
            state=dict(type="str", default="present", choices=["present", "absent", "enabled", "disabled"]),
            password=dict(type="str", no_log=True),
            display_name=dict(type="str"),
            email=dict(type="str"),
            quota=dict(type="str"),
            groups=dict(type="list", elements="str"),
            append_groups=dict(type="bool", default=False),
            settings=dict(type="dict"),
        ),
        supports_check_mode=True,
    )

    params = module.params
    apply_env_defaults(params, module)
    if not params.get("occ_path"):
        module.fail_json(msg="occ_path is required (set parameter or NEXTCLOUD_OCC_PATH env var)")

    name = params["name"]
    state = params["state"]
    result = {"changed": False}

    info = get_user_info(module, params, name)
    user_exists = info is not None

    result["user"] = {
        "name": name,
        "exists": user_exists,
        "enabled": bool(info.get("enabled", False)) if info else False,
    }

    # --- absent ---
    if state == "absent":
        if not user_exists:
            module.exit_json(**result)
        if module.check_mode:
            result["changed"] = True
            module.exit_json(**result)
        occ_run(module, params, ["user:delete", name])
        result["changed"] = True
        result["user"]["exists"] = False
        module.exit_json(**result)

    # --- present / enabled / disabled ---
    if not user_exists:
        if state == "disabled":
            module.fail_json(msg="Cannot disable non-existent user '%s'" % name)
        password = params.get("password")
        if not password:
            module.fail_json(msg="'password' is required to create a new user")
        if module.check_mode:
            result["changed"] = True
            module.exit_json(**result)
        argv = ["user:add", name, "--password-from-env"]
        if params.get("display_name"):
            argv.extend(["--display-name", params["display_name"]])
        if params.get("groups"):
            for g in params["groups"]:
                argv.extend(["--group", g])
        occ_run(module, params, argv, check_rc=True, environ_update={"OC_PASS": password})
        result["changed"] = True
        user_exists = True
        info = get_user_info(module, params, name) or {}

    # Enable / disable
    is_enabled = bool(info.get("enabled", True)) if info else True
    if state == "disabled" and is_enabled:
        if not module.check_mode:
            occ_run(module, params, ["user:disable", name])
        result["changed"] = True
    elif state in ("enabled", "present") and not is_enabled:
        if not module.check_mode:
            occ_run(module, params, ["user:enable", name])
        result["changed"] = True

    # Settings: display_name, email, quota
    if params.get("display_name") and info and info.get("display_name") != params["display_name"]:
        if not module.check_mode:
            occ_run(module, params, ["user:setting", name, "settings", "display_name", "--value", params["display_name"]])
        result["changed"] = True

    if params.get("email") and info and info.get("email") != params["email"]:
        if not module.check_mode:
            occ_run(module, params, ["user:setting", name, "settings", "email", "--value", params["email"]])
        result["changed"] = True

    if params.get("quota") is not None and info:
        current_quota = info.get("quota", "")
        if isinstance(current_quota, dict):
            current_quota = current_quota.get("quota", "")
        if str(current_quota) != str(params["quota"]):
            if not module.check_mode:
                occ_run(module, params, ["user:setting", name, "files", "quota", "--value", params["quota"]])
            result["changed"] = True

    # Custom settings
    if params.get("settings") and info:
        for setting_key, setting_value in params["settings"].items():
            parts = setting_key.split(None, 1)
            if len(parts) != 2:
                module.fail_json(msg="settings key must be in 'app key' format, got: '%s'" % setting_key)
            app_name, key_name = parts
            run = occ_run(module, params, ["user:setting", name, app_name, key_name], check_rc=False)
            current = run["stdout"].strip() if run["rc"] == 0 else None
            if current != str(setting_value):
                if not module.check_mode:
                    occ_run(module, params, ["user:setting", name, app_name, key_name, "--value", str(setting_value)])
                result["changed"] = True

    # Group membership
    if params.get("groups") is not None and state in ("present", "enabled"):
        desired_groups = set(params["groups"])
        current_groups = set(get_user_groups(module, params, name))
        append = params.get("append_groups", False)

        groups_to_add = desired_groups - current_groups
        groups_to_remove = set() if append else (current_groups - desired_groups)

        if groups_to_add:
            existing_groups = get_group_list(module, params)
            for g in groups_to_add:
                if g not in existing_groups:
                    if not module.check_mode:
                        occ_run(module, params, ["group:add", g])
                    result["changed"] = True

        for g in groups_to_add:
            if not module.check_mode:
                occ_run(module, params, ["group:adduser", g, name])
            result["changed"] = True

        for g in groups_to_remove:
            if not module.check_mode:
                occ_run(module, params, ["group:removeuser", g, name])
            result["changed"] = True

    # Refresh user info for return
    if not module.check_mode:
        info = get_user_info(module, params, name)
    result["user"] = {
        "name": name,
        "exists": True,
        "enabled": bool(info.get("enabled", True)) if info else True,
        "display_name": info.get("display_name", "") if info else "",
        "email": info.get("email", "") if info else "",
        "groups": get_user_groups(module, params, name) if not module.check_mode else [],
    }
    module.exit_json(**result)


if __name__ == "__main__":
    main()
