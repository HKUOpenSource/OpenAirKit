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
trust in arbitrary code. Existing administration access is unchanged. To revoke
only this permission, an administrator removes `/etc/sudoers.d/aoc-maintenance`.
The bootstrap rejects existing maintenance configuration unless an administrator
explicitly supplies `--replace-approval PREVIOUS_SHA256`. Replacement verifies the
old protected payload and installed helper, requires the same account and role,
and preserves the exact sudoers contents. It holds the maintenance lock, saves
the old access files and restores them if activation fails. Non-root `--check`
validates the new archive/policy only; privileged activation checks the old state.

Validation for this change: nine boundary tests cover exact role policies,
non-privileged review, hash tampering, archive traversal/links, extra payload code,
unsafe ownership/modes, additional arguments, fixed child environments, explicit
approval replacement and restoration after failed activation. The
question is how to automate reviewed project maintenance without storing a password.
The call path is `build -> bootstrap.unpack/check_policy -> protected installation ->
aoc-maintain.main -> approved -> execute`. Both target devices passed non-root
archive and native `visudo` checks. After one-time administrator activation, both
targets passed passwordless `verify` and `status`; application deployment passed
on both devices. Spark rollback/reinstallation and connectivity upgrade also passed.
The updated Jetson installer verifies existing packaged files, root ownership and
permissions, runtime paths and dependencies before reusing a release after rollback.
The administrator-approved update is activated on both devices. Jetson previous-
version rollback, fresh installation and same-release rollback/reinstallation
passed on hardware. System
Wi-Fi control is outside this policy and still requires normal administration.

The one-time `repair-connectivity-manifest.py` addresses the first connectivity
updater's missing outer radio manifest update. It requires separate administrator
execution; the existing helper does not authorize arbitrary repair code. With the
radio stopped and the maintenance lock held, it verifies an original root-owned
backup, the reviewed runtime/image, and every unaffected file. Only three outer
manifest hashes change; a saved original and failed-write restoration protect the
transaction. It does not change services or broaden sudo permissions. The updated
upgrader includes the parent manifest in normal validation and rollback. That code
is now deployed through a new reviewed approval and passed a production
connectivity upgrade, with all 12 core services healthy afterward.

The first operator run stopped before any write at the `bin` directory ownership/
mode check. The old installer preserved staged directory modes. The revised repair
requires the release root to be private (`0700`), checks every listed file's parent
directory, and can remove group-write permission from root:root directories inside
that boundary. It rejects symlinks, other owners/groups and world-writable
directories; regular files still undergo the original strict permission and hash
checks. A failed repair restores the prior directory modes, and a successful repair
saves the mode changes beside the original manifest. This behavior passed an
isolated Linux test with real root-owned `0775` directories, without host mounts,
as well as writable-file rejection and permission rollback tests.
