# CodeGraph workflow

When `.codegraph/` exists at the repository root, use CodeGraph before text
search to locate symbols and call paths. Ask one concrete question that names
the behavior, likely symbol or file, then verify the returned source before
editing.

Record four items in the change description:

1. the question asked;
2. the relevant call path;
3. the affected application and release boundary;
4. the tests that cover the change.

`codegraph.json` defines the repository configuration. Run
`scripts/check-codegraph.sh` to validate it. If `.codegraph/` is absent, do not
generate an index implicitly; use normal repository tools and state that the
graph was unavailable.
