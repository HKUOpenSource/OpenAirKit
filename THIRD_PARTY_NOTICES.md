# Third-party notices

Runtime dependencies are installed from the platform-specific lock files and
the offline wheelhouse produced for a release. Each release records the exact
dependency set and includes its generated license material in
`THIRD_PARTY_LICENSES/` and `THIRD_PARTY_DEPENDENCIES.json`.

Upstream source revisions and container image digests are pinned in
`config/upstreams.json` and `config/images.lock.json`. A dependency update must
update the relevant lock, notices, tests and release audit evidence together.

Both web consoles use Astryx Core, Neutral and Charts at the identical pinned
version `0.6.2-canary.d72e4d6` (MIT), StyleX 0.19.0 (MIT), and Lucide React 1.18.0
(ISC, with its included additional icon notices). Their exact transitive
versions are recorded in each frontend's `package-lock.json`.

Frontend builds emit `dist/THIRD_PARTY_NOTICES.txt` from bundled dependencies'
license files, which is copied with the static frontend into release payloads.
Missing license text fails the build. Pinned upstream copies for npm tarballs
that omit their license are documented in
[the shared UI package](packages/console-ui/README.md).
