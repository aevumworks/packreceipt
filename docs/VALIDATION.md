# v0.1.0 validation

Date: 2026-11-11 (Asia/Shanghai).

Environment actually used: Windows 11 Enterprise 10.0.26200, CPython 3.14, Ego Lite / Chromium 156. No mocks of the filesystem in the main sender/recipient demo; fixture content is original synthetic design work.

## Automated core checks

`python -m unittest discover -s tests -v`: **20 passed**, zero skipped. Tests include Chinese/nested and zero-byte files, files larger than the read chunk, byte changes with equal size and preserved mtime, all comparison statuses, duplicate-content ambiguity, same-path priority, a real Windows junction, a mutation injected during hashing, manifest boundary validation, HTML escaping, output protection, and CLI return codes.

A Windows-specific metadata bug was found before release: DirEntry.stat reports zero file identifiers, and lstat/fstat disagree on ctime in this runtime. The implementation now compares the shared identity/size/mtime fields across APIs and complete stamps within each API. The same tests passed after correction. There is no silent fallback to a successful result.

## Complete synthetic scenario

`python examples/create_demo.py examples/demo` created two 7-file deliveries and two simulated received packages. Independent expected-count assertions passed:

| Scenario | Modified | Same-content move | Added | Removed | Unchanged | Matches |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| v1 → v2 | 2 | 1 | 1 | 1 | 3 | false |
| v2 → incorrect receipt | 1 | 0 | 1 | 1 | 5 | false |
| v2 → corrected receipt | 0 | 0 | 0 | 0 | 7 | true |

The wrong poster and correct poster both have 620 bytes; their SHA-256 differs. File count alone is also insufficient: the bad received package still contains 7 files because an extra note offsets the missing guide.

## Browser checks

The actual generated `file://` reports were opened in an isolated Ego Lite Agent Space. Checked all/status filters, Chinese path search, empty results, keyboard expansion, 64-character hashes, print-button dispatch, default display for a matching receipt and absence of horizontal overflow at 1280×1000 and 390×844 emulation. Original screenshots were visually inspected. A local report reload produced no Runtime exception or error-log event and no external resource request. Print-button dispatch is verified; actual operating-system printing and PDF pagination have not been accepted.

The test monitor initially lost a custom window variable after navigation; this was a browser-test harness error, not an application error. Runtime/CDP events were used for the relevant reload evidence instead. No physical phone, macOS, Linux, huge directory, hostile concurrent mutation or signature authentication validation is claimed.

## Reproduce

Use a new demo output directory:

```sh
python -m unittest discover -s tests -v
python examples/create_demo.py examples/demo
python scripts/build_release.py
```

The demo generator stops if the output directory exists. The CLI refuses existing outputs unless `--force` is explicit. Reports show data computed from files, and the source example artwork is included under MIT.
