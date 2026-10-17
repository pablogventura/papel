# Papel

Print a file as a grid of dots on A4, then recover it from a scan.

The PDF is the sheet you send to the printer. The backup is the paper. Scan that sheet at 300 dpi and `papel decode` rebuilds the file. Sheet order does not matter. If a sheet is missing, nothing is written.

This is a new format. It does not read PaperBack bitmaps.

## Install

Python 3.11 or newer.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[test]"
```

## Print

```bash
.venv/bin/papel encode FILE -o backup.pdf
```

That writes one or more A4 pages. A laser printer can use the default, black on white. For a color printer:

```bash
.venv/bin/papel encode FILE -o backup.pdf --mode cmy
```

`cmy` stores one bit in each of cyan, magenta, and yellow. At the default dot size it holds about three times as much as black and white, including a small misregistration between inks.

| Mode | Use | Payload per A4 page |
| --- | --- | --- |
| `bw` (default) | Laser, grayscale scan | 25,768 bytes |
| `cmy` | Color printer, color scan | 77,504 bytes |

A file larger than one page becomes several sheets. The whole file is compressed with zlib when that makes it smaller. Each page carries a CRC of the original file and Reed-Solomon parity (32 bytes per 255).

The default dot is 0.45 mm (`--module-mm`). At 300 dpi that is about five pixels per dot. Dots smaller than 0.40 mm do not survive the print-and-scan noise used in the tests. The scanner needs at least three pixels per dot (0.254 mm at 300 dpi); the default stays above that.

A short file leaves most cells white, so the page looks almost blank. The dots that do exist are spread across the sheet so a stain does not land on the same correction block. A file that fills the page looks dense. `ejemplo.pdf` is that case: page 1 is black and white, page 2 is color.

## Scan

Scan at 300 dpi. Use grayscale for `bw` and color for `cmy`. Keep the whole page, including the corner marks and the white margin.

```bash
.venv/bin/papel decode scan.png another.png -o FILE
```

Images can be PNG, JPEG, or TIFF. A PDF is accepted too: each page is rasterized at 300 dpi, which is how you can try a round trip without a printer.

```bash
.venv/bin/papel decode backup.pdf -o FILE
```

Corners are finder marks. The top edge and the left edge are timing tracks, and they fix the rotation. Duplicate scans of the same sheet are fine. Two different files in one command are not.

## Tests

```bash
.venv/bin/pytest
```

The tests rasterize the PDF at 300 dpi and add blur, noise, rotation, shift, and a stain. Color pages also get 0.1 mm of ink misregistration. A heavier damage profile must fail instead of returning a wrong file.
