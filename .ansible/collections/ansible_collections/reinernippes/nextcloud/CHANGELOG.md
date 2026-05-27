# Changelog

## 1.0.0 — Initial Release

- Initial release of the `reinernippes.nextcloud` Ansible collection
- Modules: `occ_app`, `occ_command`, `occ_config_app`, `occ_config_system`, `occ_group`, `occ_info`, `occ_maintenance`, `occ_user`
- Common parameters: `occ_path`, `php_bin`, `web_user`, `chdir` (with environment variable fallbacks)
- Test playbook with `fake_occ.py` fixture
