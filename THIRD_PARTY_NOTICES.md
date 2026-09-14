# Third-party notices

Runtime dependencies are installed from the platform-specific lock files and
the offline wheelhouse produced for a release. Each release records the exact
dependency set and includes its generated license material in
`THIRD_PARTY_LICENSES/` and `THIRD_PARTY_DEPENDENCIES.json`.

Upstream source revisions and container image digests are pinned in
`config/upstreams.json` and `config/images.lock.json`. A dependency update must
update the relevant lock, notices, tests and release audit evidence together.
