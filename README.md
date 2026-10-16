# Bilder trennen

A small local web tool for splitting scans of double pages (e.g. open books or
letter bundles) into single pages. It works through every image in `import/`,
shows it in the browser, lets you place the cut line, and writes the result in
two flavours:

| Folder         | Content                                                              |
|----------------|----------------------------------------------------------------------|
| `export/jp2/`  | Lossless JPEG 2000, full resolution, with a 5 % overlap on each side of the cut |
| `export/jpeg/` | JPEG, long edge max. 2500 px, quality 85, **no overlap** – meant for upload to [Transkribus](https://www.transkribus.org/) |

Everything runs locally; the server only listens on `127.0.0.1`. Nothing is
uploaded anywhere.

## Requirements

- Python ≥ 3.9
- [Pillow](https://python-pillow.org/) (installed automatically by the start methods below)
- A modern web browser

## Start

```sh
./start.sh
```

`start.sh` uses the local `.venv` and creates it (with Pillow) if it is missing.
Alternatively, with [uv](https://docs.astral.sh/uv/):

```sh
uv run script/bilder-trennen.py
```

The browser opens at <http://127.0.0.1:8765>.

Options:

| Option          | Meaning                                                           |
|-----------------|-------------------------------------------------------------------|
| `--port N`      | Use another port (default `8765`)                                 |
| `--keep`        | Keep the originals in `import/` (default: delete after a successful export) |
| `--no-browser`  | Do not open the browser automatically                             |

## Usage

1. Put the scans into `import/` (`.jp2`, `.jpg`, `.png`, `.tif`, `.bmp`, `.webp`; files are processed in natural order).
2. Start the tool. Drag the cut line or click into the image to position it.
3. Choose an action:

| Button               | Key          | Result                                                                 |
|----------------------|--------------|------------------------------------------------------------------------|
| Trennen              | `S`          | Split at the line → `name_0` and `name_1` as `.jp2` **and** `.jpg`     |
| nicht beschneiden    | `Enter`      | Export the whole image unchanged → `name.jp2` and `name.jpg`           |
| Überspringen         | `→`          | Leave the file in `import/` and go to the next one                     |
| ←                    | `←`          | Go back                                                                |

Fine adjustment of the line: `A` / `D` (0.1 %), with `Shift` 1 %.

Safety: existing files in `export/` are never overwritten (the action aborts
with an error and the original stays in place). The original is only removed
after all outputs were written (the JP2 files are re-read as a check).

## Configuration

Constants at the top of [`script/bilder-trennen.py`](script/bilder-trennen.py):

| Constant         | Default | Meaning                                  |
|------------------|---------|------------------------------------------|
| `OVERLAP`        | `0.05`  | Overlap per side of the cut (JP2 only), relative to image width |
| `JPEG_MAX_SIZE`  | `2500`  | Long edge of the JPEG in pixels          |
| `JPEG_QUALITY`   | `85`    | JPEG quality                             |
| `PREVIEW_SIZE`   | `2400`  | Long edge of the browser preview         |

## Project layout

```
script/bilder-trennen.py   server and image processing
script/index.html          browser UI (single file, no external resources)
start.sh                   start script
import/                    input (not tracked by git)
export/                    output (not tracked by git)
```

## Licence

Code: [MIT](LICENSE) © 2026 Martin Anton Müller.

Dependency: Pillow is distributed under the [MIT-CMU (HPND) licence](https://github.com/python-pillow/Pillow/blob/main/LICENSE), which is compatible with MIT. It is installed at runtime and not bundled in this repository.

**Your scans are not covered by this licence.** The repository ignores `import/` and `export/` on purpose. Check the rights of the source material (archive, library, estate) yourself before publishing any images.
