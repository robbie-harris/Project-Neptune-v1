# Rejected P3c native candidates

**NOT ACTIVE — NOT PART OF NORMAL BUILD — FAILED ACCEPTANCE.**

These patches are retained solely as evidence of the bounded P3c investigation.
Neither Dockerfile nor any launch/profile applies them. `apply.py` runs only by
explicit manual invocation against a disposable pinned checkout; it must not be
added to normal build or startup automation.

Candidate 1 renders all pending views. Candidate 2 also substitutes framebuffer
readback for texture readback. Both failed the >=5 Hz / <0.5 s camera gate.
The accepted P3 perception profile uses the original native library and reduces
the rendering budget instead. Measurements and audit are in
`docs/PERCEPTION_INTEGRATION.md`.
