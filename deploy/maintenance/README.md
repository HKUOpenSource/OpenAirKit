# Restricted maintenance access

The root-owned `/usr/local/sbin/aoc-maintain` helper permits exact operations for
one device role. Initial installation requires an administrator's password in the
device terminal. No password is stored or sent to the application or agent.
Initialization creates access configuration only; it does not install an application,
restart a service, change modem settings, or enable boot startup.

The bootstrap checks the externally supplied SHA-256 of a private snapshot of the
approval archive, rejects links/path traversal/unlisted files, checks `visudo`
syntax, and copies the approved payload under `/opt/agentic-ocudu/maintenance`.
Only root can change that payload, the helper, its configuration, or its state.
The sudoers rule enumerates exact action arguments with `NOPASSWD: NOSETENV`; it
never grants a generic shell, Python interpreter, arbitrary path or wildcard.
The helper verifies hashes and file ownership on every operation, uses a clean
child environment and serializes operations using a protected lock.

Build from the already verified application release directory:

```sh
python3 deploy/maintenance/build.py jetson --release /path/to/verified/stage --output /new/output
# Use spark for Spark; its approval also includes the reviewed connectivity updater.
```

Transfer `bootstrap.py` and `approved.tar.gz` to a private device directory. Before
any privileged installation, validate the archive and generated sudoers as the SSH
user (replace the placeholders with the independently recorded digest and account):

```sh
python3 -I bootstrap.py --archive approved.tar.gz --sha256 DIGEST --user ACCOUNT --check
sudo /usr/bin/python3 -I bootstrap.py --archive approved.tar.gz --sha256 DIGEST --user ACCOUNT
sudo -n /usr/local/sbin/aoc-maintain verify
```

Both roles allow `status`, `verify`, `install`, `rollback`, `start`, and `stop`.
Jetson additionally permits `ue-status`, `ue-maintenance`, `ue-resume`, `ue-recover`
and `ue-job` (only the recovery job started by this helper). Spark additionally
permits `radio-start`, `radio-stop`, `radio-restart`, `core-start`, `core-stop`,
`core-restart`, and `connectivity-upgrade`. No operation accepts extra arguments.
Install/rollback affect the project and can interrupt its data connection; review
and sequence them as normal deployment work. The Jetson installer stops the
platform first; after an install failure, inspect status and use the saved rollback
checkpoint when available. Rollback is limited to the checkpoint created by this
helper's installation. New installs without existing authentication are rejected.

This approval covers the exact packaged release. Future changed release code needs
another administrator-approved bundle; a checksum by itself does not establish
trust in arbitrary code. Existing administration access is unchanged. To revoke this permission without disturbing general administrator access,
remove `/etc/sudoers.d/aoc-maintenance`. Existing maintenance installations
refuse overwrites unless `--replace-approval PREVIOUS_SHA256` is passed; the
bootstrap verifies the previous protected payload, helper, account and role,
holds the maintenance lock, backs up the prior access files, and restores them
if activation fails. System Wi-Fi management remains outside this allowlist and
requires standard administrator privileges.
