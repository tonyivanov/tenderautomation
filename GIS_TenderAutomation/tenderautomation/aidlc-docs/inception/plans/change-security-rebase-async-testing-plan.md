# AI-DLC Change Plan — Security and Merge Readiness

1. Preserve `backup/anatoly-before-cleanup` and replay the cumulative feature diff on `main` without secrets.
2. Correct Core async contracts and Web authorization/mutation behavior.
3. Correct Bidzaar incremental/expiry logic and stable-ID cache joins.
4. Reconcile Docker/Compose and add test/security CI gates.
5. Run example and property tests, history/secret/hygiene checks, and record evidence.
6. After CI feedback, constrain Gitleaks to commits introduced by the MR or push and add a
   regression check for the commit range; retain full forensic findings as rotation input.

Security Baseline and Property-Based Testing extensions are blocking. Remote history is not updated until local gates are green and explicit approval is received.

Approval: `[Answer]: A — approved by user`.
