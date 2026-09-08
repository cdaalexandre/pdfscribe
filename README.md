# pdfscribe

Faithful page-by-page transcription of PDF files into Markdown. Native
text where the page has a healthy text layer, OCR where it does not,
decided **per page** and never per document.

![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Type checked: mypy strict](https://img.shields.io/badge/mypy-strict-blue)
![Lint: ruff](https://img.shields.io/badge/ruff-checked-261230)

---

## Fidelity contract

pdfscribe is a scribe, not an editor. It copies what the page shows and
notes in the margin what it could not read.

1. Output is **literal** by default: no de-hyphenation, no line joining,
   no spelling fixes, no header or folio stripping.
2. Normalization is opt-in (`--normalize`) and every applied operation is
   recorded in a log next to the output.
3. Every page emits a provenance marker, always:
   `<!-- p.N | fonte: nativo|ocr | conf: 0.00-1.00 | folha: X|? -->`
4. An OCR page below the confidence threshold is flagged in its marker.
   A page with no characters after both paths is marked `vazia`, never
   omitted.
5. No page disappears: `len(pages_out) == doc.page_count` is a mandatory
   test assertion.
6. The application never summarizes or improves text. That is a job for
   an LLM downstream, outside this repository.

## Architecture

Hexagonal (ports and adapters), after Percival & Gregory.

```
src/pdfscribe/
| adapters/         # I/O boundaries: PyMuPDF reader, rasterizer, tesseract, writer
| domain/           # Pure logic: page classification, fidelity markers, splitter
| service_layer/    # Orchestration: read -> classify -> extract|ocr -> mark -> write
| entrypoints/      # argparse CLI
| log.py            # get_logger + setup_logging
```

- `domain/` depends on nothing else in the project.
- `adapters/` hides every external library behind a `Protocol`.
- `service_layer/` receives adapters by parameter, so it is testable
  with Fakes rather than `mock.patch`.

## Roadmap

| PR  | Scope                                                       | Status |
| --- | ----------------------------------------------------------- | ------ |
| PR0 | Bootstrap, CI, fidelity value objects and markers           | done   |
| PR1 | Native extraction per page, marker, writing, `--dry-run`    | next   |
| PR2 | Quality classifier, rasterizer, tesseract OCR, confidence   |        |
| PR3 | Byte-based splitter (~3 MB parts) and run log               |        |
| PR4 | `--normalize` opt-in with an operations log                 |        |

## Development

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Phase C, all four gates green before any commit:

```powershell
ruff check .; ruff format --check .; mypy src; pytest
```

OCR needs the `tesseract` binary plus the `por` language data; it is not
a pip dependency. On Windows use the UB-Mannheim installer and add it to
PATH. Tests that need it skip themselves when it is absent.

## Encoding

UTF-8 without BOM everywhere, LF line endings enforced by
`.gitattributes` from the initial commit. Transcription output is written
with `write_bytes` so that no line ending is silently translated.

## License

MIT
