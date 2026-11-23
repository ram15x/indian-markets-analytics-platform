# Engine C (Rust) on Windows

Status: Linux, and one Windows run on 2026-11-24 (280 passed, nothing skipped). Original note: built and tested on Linux only. Not verified on Windows by the assistant (its shell is Linux). A Windows wheel
is present in `engine_c/target/wheels/` (git-ignored), but no run of the 9 engine-C tests on Windows has been recorded.

To check it yourself, in PowerShell from the project root:

    pip install --force-reinstall engine_c\target\wheels\imap_engine_c-0.1.0-cp310-abi3-win_amd64.whl
    python -m pytest -q -rs

If the engine-C tests no longer show as skipped and all pass, record the output in `docs/ENGINE_RESULTS.md`.
If they fail, paste the error; the app keeps working without engine C (two engines still must agree).
