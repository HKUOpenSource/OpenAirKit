# Acceptance records

This directory stores redacted evidence for completed roadmap work. The
[roadmap](../roadmap.md) is the only checklist; records do not maintain a
second completion state.

Name a record `YYYY-MM-DD-<task-or-milestone>.md` and include:

- date, source revision, application version and target environment;
- release or configuration checksums;
- the exact bounded operation or test;
- expected and observed results;
- rollback result and remaining limitations.

Hardware work requires hardware evidence. Generated data, simulator output or
unit tests cannot be presented as a live deployment result. Failed and skipped
checks remain visible.

Store only redacted summaries. Subscriber credentials, private addresses,
passwords, databases, raw logs and packet captures belong in ignored or
access-controlled deployment storage. IMS, SIP and voice are outside the
current acceptance gate.
