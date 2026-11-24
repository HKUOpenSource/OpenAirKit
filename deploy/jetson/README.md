# Jetson deployment

These files install and manage the `aoc_jetson` application.
Installation starts the loopback Web service only. The independent `commission`
action binds the local SIM and management settings without stopping external
services. It automatically selects the installed application runtime. Both
services remain disabled at boot.

Start prepares the configured data routes and resumes observation with recovery
paused. Stop releases services before journal-aware owned-route cleanup. The
release includes the operator scripts; the installed manager also works
directly with administrator sudo. See the paired [setup guide](../../docs/setup-ue-jetson.md)
and [operations guide](../../docs/jetson-operations.md).
