# Spark Platform

The Spark Platform owns host, RAN and Open5GS observation plus bounded stack
operations at `127.0.0.1:8877`. Its backend is `backend/aoc_spark`, the React
frontend is in `frontend`, contracts are in `contracts`, and deployment units
are in `/deploy/spark/platform`. It keeps evidence-based state and has no
runtime dependency on another application or monitoring database.

```sh
npm ci --prefix apps/spark-platform/frontend
npm run build --prefix apps/spark-platform/frontend
PYTHONPATH=apps/spark-platform/backend python3 -m unittest discover -s apps/spark-platform/tests -p 'test_*.py'
```
