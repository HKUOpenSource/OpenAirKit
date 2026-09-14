# Internal release policy

Jetson and Spark are released independently. Jetson uses version `0.3.0` and
Spark uses version `0.1.0`; each release records source revision, manifest
checksum, locked dependencies, wheelhouse and rollback point.

Release audits reject the other platform, `archive/`, generated output,
symlinks, mutable dependencies and production data. Installers do not enable
boot startup or modify the other platform's stack.
