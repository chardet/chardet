# Glossary

One line per term, pointing at the module that owns it. `CONTEXT.md` has the longer domain model.

- **Window** (examination window): `data[:max_bytes]`, the bytes the verdict is about; every answer must decode it under the name the caller sees. Owned by the `max_bytes` option (`_request.DetectionRequest`).
- **Evidence cap**: how much of the window a filtering, validation, or scoring stage reads before its answer counts as converged; `_utils.EVIDENCE_CAP_BYTES`, ADR-0006.
- **Detection request**: one call's resolved options and the run-then-render sequence they drive; `_request.DetectionRequest`.
- **Rendering**: turning ranked pipeline results into the dicts callers get, with the superset remap and display names applied; `DetectionRequest.render`.
- **Public name**: the encoding name the caller sees after the output remaps; `output_names`.
- **Superset**: the codec fact that a Windows/CP code page stands in for an encoding (`iso8859-1` -> `cp1252`); `registry.EncodingInfo.superset`, ADR-0007.
- **Preferred superset**: the frozen selection of superset pairs the `prefer_superset` option applies, public as `UniversalDetector.LEGACY_MAP`; `output_names.PREFERRED_SUPERSET`, ADR-0007.
- **Rank correction**: one of the chained fixes to the statistical ranking, such as dead-heat superset promotion or the decode-safety flip; `pipeline/postprocess.py`.
- **Confusion group**: encodings that bigram scoring cannot reliably tell apart, settled by distinguishing bytes; `pipeline/confusion.py`.
