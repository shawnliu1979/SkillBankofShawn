# SheetMark

SheetMark is a local-only Skill and Python converter for turning Excel workbooks into Markdown tables.

It supports `.xlsx`, `.xlsm`, and legacy `.xls` files. Workbook contents are processed on the local machine and are never uploaded to an external API.

## Features

- Convert all worksheets or selected worksheets to Markdown.
- Preserve worksheet names as Markdown section headings.
- Keep merged-cell content only in the top-left cell of each merged range.
- Export embedded worksheet images to a local sibling directory and reference them from Markdown.
- Escape Markdown-sensitive cell content, including pipes and line breaks.
- Read formula text by default, or read cached formula results with `--values`.
- Support macOS, Windows 10/11, and Linux when the required local tools are available.
- Return a clear installation prompt when a required dependency is missing.

## Install Skill

For a project-level Skill, copy this directory to:

```text
<your-project>/.github/skills/sheetmark/
```

The installed directory should contain at least:

```text
sheetmark/
├── SKILL.md
├── README.md
└── sheetmark.py
```

For a personal Skill, place it at one of these supported locations:

```text
~/.copilot/skills/sheetmark/
~/.agents/skills/sheetmark/
~/.claude/skills/sheetmark/
```

`SKILL.md` is the entry point. `README.md` is documentation for people; it is not a replacement for `SKILL.md`.

## Requirements

Python 3.10 or newer and the local `openpyxl` package are required for `.xlsx` and `.xlsm` files.

macOS/Linux:

```bash
python3 -m pip install openpyxl
```

Windows PowerShell:

```powershell
py -m pip install openpyxl
```

Legacy `.xls` files additionally require LibreOffice. SheetMark uses LibreOffice locally to convert the old binary workbook to a temporary `.xlsx`, then processes that file with `openpyxl`.

macOS, when Homebrew is available:

```bash
brew install --cask libreoffice
```

On Windows, install LibreOffice through an approved local software source. If it is installed in a non-standard location, set:

```powershell
$env:SHEETMARK_SOFFICE = 'C:\Program Files\LibreOffice\program\soffice.exe'
```

SheetMark does not install Python packages or LibreOffice automatically, and it does not fall back to a cloud service.

## Usage

Use SheetMark when you want a local Excel workbook read, inspected, or converted to Markdown. Provide the workbook path in your request and describe any optional worksheet or output requirements.

Example requests:

- "Convert `/path/to/workbook.xlsx` to Markdown."
- "Convert `/path/to/workbook.xlsm`, but include only the `Sales` and `Summary` worksheets."
- "Read `/path/to/formulas.xlsx` and use cached formula results instead of formula text."
- "Convert `/path/to/report.xlsx` without exporting embedded images."
- "Convert `/path/to/workbook.xlsx` and write the Markdown to `/path/to/output/report.md`."

- If you want to use only the SheetMark Skill, You should "/sheetmark Convert `/path/to/workbook.xlsx` to Markdown."

The Skill should:

1. Confirm that the workbook is a local `.xlsx`, `.xlsm`, or `.xls` file and that it can be read.
2. Convert all worksheets unless specific worksheet names are requested.
3. Write one Markdown section per worksheet, using the first non-empty row as the table header.
4. Preserve worksheet names as section headings, escape Markdown-sensitive cell content, and keep merged-cell values only in the top-left cell.
5. Export embedded images beside the Markdown file unless image export is disabled.
6. Report the generated Markdown path and any relevant limitations, especially for formulas, formatting, charts, pivot tables, macros, and image positions.

For formula cells, request cached values when the workbook already contains them. SheetMark does not recalculate formulas. For legacy `.xls` workbooks, the Skill requires LibreOffice locally; it converts the file to a temporary `.xlsx` before producing the Markdown output.


## Limitations

Markdown cannot fully preserve Excel formatting, column widths, row heights, charts, images' original positions, pivot tables, macros, merged-cell layout, conditional formatting, or formulas that require recalculation. `openpyxl` reads cached formula results but does not calculate formulas.

`.xlsm` macros are not executed.

## Privacy

SheetMark is designed for local processing. It does not use cloud document services, external extraction APIs, or remote spreadsheet URLs.
