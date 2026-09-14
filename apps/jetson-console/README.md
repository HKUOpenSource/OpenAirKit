# Jetson Console

The Jetson Console owns the modem-facing application and `127.0.0.1:8878`.
Its backend is `backend/aoc_jetson`, the React frontend is in `frontend`, and
deployment units and bounded installers are in `/deploy/jetson`. It preserves
the verified OCUDU/Open5GS data contract, does not control Spark, and owns its
configuration and state database.

```sh
npm ci --prefix apps/jetson-console/frontend
npm run build --prefix apps/jetson-console/frontend
PYTHONPATH=apps/jetson-console/backend python3 -m unittest discover -s apps/jetson-console/tests -p 'test_*.py'
```
