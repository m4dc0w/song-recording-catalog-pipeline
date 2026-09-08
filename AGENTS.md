# AI Agent Operating Guidelines & Project Constraints

This file defines persistent rules, constraints, and conventions that all AI agents working on this codebase must strictly observe.

## 1. Scratch Files & Temporary Scripts
- **NEVER create temporary scripts, scratch files, or test spikes in the repository root or source directories.**
- All ephemeral testing scripts, experiments, or diagnostic code must either:
  - Be executed inline (e.g., `python3 -c "..."` or standard shell commands), OR
  - Be written exclusively to the system temporary directory (`/tmp/`), with cleanup upon completion.
- Keep the project tree clean and committed only to functional codebase artifacts.

## 2. Testing & Verification Standards
- Permanent unit tests must be colocated with their corresponding modules (e.g., `module_test.py`) or in dedicated orchestrator test suites.
- Always run the full unit test suite (`python3 run_tests.py`) and verify that all tests pass without regressions before completing any task.
- Ensure all mocked external calls (Planning Center API, Gemini API, FFmpeg) accurately reflect real-world contracts and parameter signatures.

## 3. Configuration & Secrets
- Never commit secrets or credentials.
- In `.env.example`, keep optional configuration variables commented out with clear explanatory comments so users can uncomment them as needed without accidentally defining placeholder values.
