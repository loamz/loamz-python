# Vendored API descriptions

`contracts/<engine>/v1/openapi.yaml` is the engine's public API as it was when this SDK was written against it; `SHA256` is its hash and `COMMIT`
the engine commit it came from. The SDK's tests hold every call the client makes to it (`OPERATIONS` in `loamz/data/operations.py`).
To move to a newer engine: `contracts/vendor.sh data`, update `OPERATIONS` and the client, run the tests, and bump the SDK's version
(its major follows the engine's `/api/vN`). Not yet done: generating models from the spec, and `oasdiff breaking` in the engine's CI.
