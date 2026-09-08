#!/usr/bin/env bash
# Compatibility entry point; canonical implementation is harness.py.
exec python3 "$(git rev-parse --show-toplevel)/.codex/hooks/harness.py" detect-feedback-signal
