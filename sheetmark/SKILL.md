---
name: sheetmark
description: "Convert local Excel workbooks to Markdown tables with Python. Use when reading, extracting, or converting local .xlsx, .xlsm, or .xls files. Runs offline, never uploads workbook contents, and uses LibreOffice locally for legacy .xls files."
argument-hint: "Excel file path and optional output path or worksheet name"
user-invocable: true
---

# SheetMark

Convert a local Excel workbook into readable Markdown tables with the bundled [converter](./sheetmark.py). This Skill is local-only: do not upload workbooks, call cloud APIs, download converters, or access remote spreadsheet URLs.

## When to Use

- The user asks to read, inspect, extract, or convert a local `.xlsx`, `.xlsm`, or `.xls` file.
- The user wants worksheet data represented as Markdown.
- The user asks for a local, privacy-preserving Excel-to-Markdown workflow.

## Prerequisites

The first use requires Python 3.10 or newer and the local `openpyxl` package. Dependencies are intentionally not installed automatically.

macOS/Linux:

```bash
python3 -m pip install openpyxl
```

Windows PowerShell:

```powershell
py -m pip install openpyxl
```

Legacy `.xls` files additionally require a local LibreOffice installation. LibreOffice converts `.xls` to temporary `.xlsx`; the bundled converter then processes that `.xlsx` with the same local Python path.

macOS, when Homebrew is available:

```bash
brew install --cask libreoffice
```

Windows users should install LibreOffice through their approved local software source. The converter checks `soffice` on `PATH` and common installation directories. A custom executable can be supplied with `SHEETMARK_SOFFICE`.

If a prerequisite is missing, tell the user to install it using the command printed by the converter and rerun the conversion. Do not install software automatically or use an external fallback.

## Procedure

1. Confirm that the workbook path is local and readable.
2. Run [sheetmark.py](./sheetmark.py) with the workbook path.
3. Use `--sheet` once per requested worksheet, or omit it to convert all worksheets.
4. Use `-o` for an exact Markdown filename or an existing output directory.
5. Use `--values` when cached formula results are preferred over formula text.
6. Embedded worksheet images are exported to a sibling `<output-name>_images/` directory and inserted after the corresponding table. Add `--no-images` to omit them.
7. Merged cells retain their value only at the merged area's top-left cell; all other cells in that area remain empty.
8. Report the output path and mention limitations when the workbook contains formatting, charts, images, pivot tables, macros, merged cells, or formulas.

## Commands

macOS/Linux:

```bash
python3 ./sheetmark.py data.xlsx
python3 ./sheetmark.py data.xlsx --sheet "Sheet1" -o output.md
python3 ./sheetmark.py data.xlsx --sheet "Sales" --sheet "Summary" -o ./output/
python3 ./sheetmark.py formulas.xlsx --values -o formulas.md
python3 ./sheetmark.py report-with-images.xlsx -o report.md
python3 ./sheetmark.py report-with-images.xlsx --no-images -o report.md
```

Windows PowerShell:

```powershell
py .\sheetmark.py data.xlsx
py .\sheetmark.py old-file.xls -o output.md
```

Without `-o`, the Markdown file is written beside the workbook. With `-o output.md`, the script writes exactly to that file. With `-o ./output/`, the directory must already exist and the script writes `<input-name>.md` inside it.

## Output and Limitations

- Each worksheet becomes an `##` section.
- The first non-empty row is used as the Markdown header.
- Empty cells remain empty; pipes are escaped and line breaks become `<br>`.
- Merged-cell content is emitted only in the top-left cell of the merged range; the other Markdown cells remain empty.
- Embedded worksheet images are saved beside the Markdown file in `<output-name>_images/` and inserted after their worksheet table. Their precise Excel position and size are not preserved.
- `openpyxl` does not calculate formulas. Without `--values`, formula text is emitted; with `--values`, cached results are read when available.
- Markdown cannot preserve Excel formatting, charts, images, pivot tables, macros, merged-cell layout, or conditional formatting.
- For very large workbooks, recommend converting individual worksheets or opening the Markdown as source text rather than using a rendered preview.
