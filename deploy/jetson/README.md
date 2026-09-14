# Jetson deployment

These files install only the `aoc_jetson` application. Retired code, unrelated
databases and site-specific helpers are excluded from release manifests.
Installation starts the loopback Web service only; serial takeover is a
separate terminal action and both services remain disabled at boot.
