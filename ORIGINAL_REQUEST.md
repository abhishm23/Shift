# Original User Request

## Initial Request — 2026-09-21T03:45:50Z

Run an autonomous, strictly alternating two-agent cycle comprising an isolated QA Test Engineer and a Developer on the Sift commercial audit application until all edge cases, stress scenarios (up to 4–5 GB), and user-friendliness defects are resolved and verified passing.

Working directory: C:\Shift
Integrity mode: development

## Requirements

### R1. Synthetic Data Generation & Isolated Test Engineer Harness
- Generate and stage comprehensive synthetic test datasets covering edge cases (zero/negative margins, missing columns, malformed inputs, extreme scales), user-friendliness flows, and large-scale stress datasets (multi-million rows, 4 GB – 5 GB+) leveraging existing generators in test_deliverables/.
- The Test Engineer must remain completely isolated from application source code and backend logic, experiencing and validating the application solely as an end user.
- All testing must be conducted purely on-screen via the graphical user interface using browser automation (Playwright), taking screenshots and visually validating all UI elements, layout states, and error dialogues. Zero reliance on backend API or programmatic black-box endpoints.

### R2. Deliverables Logging & Cumulative Round Appending
- Start from the existing test records in C:\Shift\test_deliverables\TEST_DELIVERABLES.xlsx and C:\Shift\test_deliverables\TEST_DELIVERABLES.md.
- For each iterative testing round, append new round-specific columns (e.g., Round N Tester Status, Round N Tester Comments, Round N Developer Status, Round N Developer Comments) preserving 100% of historical test cases, baseline data, and previous round records.
- Systematically catalog all defect findings, reproduction steps, expected vs. actual results, and severity ratings.

### R3. Developer Implementation & Workspace Hygiene
- The Developer Sub-Agent inspects all open defects recorded in the test deliverable ledger and implements necessary code modifications in the application.
- For each resolved issue, the Developer records the resolution details, root cause analysis, and status in the corresponding developer columns of the test deliverable file.
- Before completing each round, the Developer Agent terminates all background tasks/processes and purges all temporary, remnant, or unused files from the workspace.

### R4. Alternating Orchestration & Strict Sub-Agent Isolation
- Sub-agents execute strictly sequentially in an alternating loop: while one agent is active, the other is completely inactive.
- Sub-agents must not communicate directly with each other or exchange private state; all information handoff occurs strictly via TEST_DELIVERABLES.xlsx and TEST_DELIVERABLES.md.
- In subsequent rounds, the Test Engineer retests all developer fixes from the screen, assesses for any regression against existing features, and updates the deliverable ledger.
- The cycle iterates autonomously until all test cases and defects are verified fixed and passing.

## Acceptance Criteria

### End-to-End Visual UI Testing
- [ ] 100% of test journeys are executed against the running UI (http://127.0.0.1:8765), verified via automated screenshots and visual element assertions.
- [ ] Zero test assertions rely on direct backend API calls or internal database inspections.

### Stress Testing & Extreme Scale
- [ ] Ingestion and preview of multi-million row datasets (including 4 GB – 5 GB files) complete within reasonable, non-frustrating time limits without crashing the UI or violating memory constraints.
- [ ] UI remains responsive with appropriate progress indicators or streaming feedback during long-running operations.

### Deliverables Integrity & State Hygiene
- [ ] TEST_DELIVERABLES.xlsx and TEST_DELIVERABLES.md have new columns appended for each round without modifying or overwriting existing historical data.
- [ ] Zero remnant temporary files or orphan background server processes remain after round completion.
- [ ] 100% of logged defect items achieve "Verified Fixed" / "Pass" status before final sign-off.
