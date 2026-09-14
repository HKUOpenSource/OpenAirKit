# Agentic-OCUDU repository guidance

Agentic-OCUDU is an independent OCUDU/Open5GS project. Keep Jetson, Spark,
the radio stack, the core stack and deployment tools in their declared
directories. Runtime UI text is English; documentation is paired English and
Simplified Chinese.

Use CodeGraph before searching source when a `.codegraph/` index exists. Record
the question, call path, impact and tests in the change description. Do not add
compatibility layers for retired paths; move historical material to `archive/`.

Never commit SIM credentials, IMSI, passwords, Tailnet addresses, production
configuration, databases, logs, captures or unsanitized screenshots. Use
Conventional Commits and run the narrowest relevant Make targets before review.
