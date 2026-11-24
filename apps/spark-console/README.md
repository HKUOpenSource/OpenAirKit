# Spark Console

The Spark Console owns host, RAN and Open5GS observation plus bounded stack
operations at `127.0.0.1:8877`. Its backend is `backend/aoc_spark`, the React
frontend is in `frontend`, contracts are in `contracts`, and deployment units
are in `/deploy/spark/platform`. It keeps evidence-based state and has no
runtime dependency on another application or monitoring database.

```sh
npm ci --prefix apps/spark-console/frontend
npm run build --prefix apps/spark-console/frontend
PYTHONPATH=apps/spark-console/backend python3 -m unittest discover -s apps/spark-console/tests -p 'test_*.py'
```
