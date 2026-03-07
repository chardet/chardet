# Pytest Fixtures for Boilerplate Reduction

## Goal

Reduce repeated setup in existing tests by extracting common patterns into pytest fixtures.

## Changes

### 1. `pipe_ctx` fixture in `test_structural.py`

Add a function-scoped fixture returning `PipelineContext()`. Replace all inline `PipelineContext()` calls in that file with the `pipe_ctx` fixture parameter.

### 2. `reset_enc_index` fixture in `test_models.py`

Add a fixture that monkeypatches `_ENC_INDEX = None` so `get_enc_index()` rebuilds from scratch. Use in `test_enc_index_alias_resolution`.

### 3. `reset_lookup_cache` fixture in `test_registry.py`

Add a fixture that monkeypatches `_LOOKUP_CACHE = None` so `lookup_encoding()` rebuilds its cache. Use in `test_build_lookup_cache_handles_invalid_codec`.

## Out of scope

- Registry lookups (`REGISTRY[name]`) — already one-liners, fixture would hurt readability
- Helper functions (`_assert_detection`) — assertion logic, not setup/teardown
- Shared test data constants — data across files is tailored to each test's needs, not truly duplicated
