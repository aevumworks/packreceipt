# Releases

## v0.1.0 · 2026-11-11

First usable release of PackReceipt.

- Scan an ordinary folder into a relative-path SHA-256 receipt without modifying source files.
- Compare two receipts, or verify a received folder against the original receipt.
- Distinguish changed bytes, unique same-content path candidates, added, removed and unchanged files. Ambiguous duplicate-content matches stay added / removed.
- Generate standalone English or Chinese HTML, with search, filters, expandable path/size/hash details and print styling. Optional comparison JSON is available.
- Explicit errors for links/reparse points, special files, detected concurrent changes, malformed manifests and accidental output replacement.
- Include an original exhibition-design example, 20 standard-library tests, bilingual instructions, MIT license, portable `.pyz` and a complete source/example `.zip`.

Usage: Python 3.10+; no third-party packages. Download `packreceipt-0.1.0.pyz`, run `python packreceipt-0.1.0.pyz --help`. Source checkout: `python -m packreceipt --help`. See the README for the full sender/recipient workflow.

Actually verified: Windows 11 10.0.26200 / CPython 3.14 / Ego Lite Chromium 156. Desktop and emulated narrow browser layouts were inspected. macOS, Linux and physical phones have not been runtime-tested.

Known limits: byte/path equality only; no signatures, format/quality inspection, archive extraction or file repair. No empty-directory/metadata/NTFS alternate-stream preservation. Scans are sequential and require a quiet folder; not an atomic snapshot. No large-tree performance claim. See README for sensitive file-name handling and schema boundaries.

All shipped source and demo content: Aevum, MIT. No third-party runtime assets.

Repository: https://github.com/aevumworks/packreceipt

Release: https://github.com/aevumworks/packreceipt/releases/tag/v0.1.0
