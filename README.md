# StampBatch — Batch Photo Watermark & Re-Check

StampBatch stamps a text or logo watermark across a whole folder of
photos, then **re-opens every output to prove the mark actually landed**
and that nothing else about the photo changed. 100% local — your photos
never leave your computer.

## What it does
- **Text or logo watermarks** — your copyright line in white or black,
  or your own logo image (transparency respected)
- **Nine-grid positioning** — any corner, edge-centre, or dead centre
- **Opacity and relative size** controls, so the mark scales correctly
  from a thumbnail to a 6000px master file
- **Tiled mode** — repeat the mark across the whole frame for
  proof/preview images
- **Platform presets** (Generic / Etsy / Instagram) that pre-tune the
  mark's relative size and margin for each platform — presets only advise
  size and margin; they never alter the photo's dimensions
- **A re-check report** (`stamp_report.md`) for every batch: each output
  is re-opened, its pixel dimensions are confirmed identical to the
  original, and the watermark area is pixel-compared against the
  original to confirm the mark is really composited
- **Originals are never modified** — results go to a separate folder

## What it deliberately does not do
- No resizing, cropping, renaming or format conversion — StampBatch is
  a watermarking tool only, so it can never silently degrade or re-frame
  your photos.
- A watermark is a deterrent, not copy protection: it raises the cost
  of stealing your images, it cannot make theft impossible.

## Verified behaviour
On a seeded set of 4 photos (1200×800 landscape, 800×1200 portrait,
3000×2000 large, 200×150 small; JPG + PNG) plus a seed logo, three
batches were run — a text corner mark (Etsy preset), a logo mark, and a
tiled text mark. 24/24 acceptance checks passed: every output re-opened
with pixel dimensions identical to its original, watermark-area pixels
measurably changed (4.7% corner text / 40.6% logo / 7.4% tiled),
opposite corners untouched (0.0%), and the originals' SHA-256 hashes
were unchanged after all runs. See TEST-RESULTS.txt in the release notes.

## Run from source
```
pip install -r requirements.txt
python stamp_batch.py photos_in photos_out --text "© Your Name" --preset etsy
python stamp_batch.py photos_in photos_out --logo logo.png --tile
```
Writes watermarked copies plus `stamp_report.md` into the output folder.
The Windows app (`gui.py`, packaged with PyInstaller) wraps the same
engine.

## Scope
JPG / PNG / WebP / BMP / TIFF photos. Output keeps the input's format
and pixel dimensions — always.
