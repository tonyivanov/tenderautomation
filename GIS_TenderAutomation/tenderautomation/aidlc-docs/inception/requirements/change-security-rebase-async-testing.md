# Change Requirements — Anatoly Branch Merge Readiness

Approved corrective scope: rebuild the feature branch on current `main`; remove secret-bearing files and generated artifacts; retain the V3 classifier/dashboard; expose async pipeline APIs; make web mutations POST-only; implement real Bidzaar `since` traversal; migrate cache association to stable `tender_id`; complete deployment inputs and automated tests.

Acceptance gates: branch descends from `origin/main`; `.env` is absent from the branch and branch-specific history; placeholders only; full pytest and Hypothesis suite passes with fixed seed; Compose validates; secret scan and `git diff --check` pass. Credential rotation remains an external blocking action.
