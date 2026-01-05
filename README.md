# unzip_cx
Automatic batch decompression tool.

## Features
- Interactive, customer-friendly TUI with guided prompts and a review step.
- Batch extraction with per-archive destination folders.
- Conflict handling (skip, overwrite, rename) and dry-run previews.
- Supports formats provided by Python's `shutil.unpack_archive`.

## Usage
### Interactive (recommended)
```bash
python -m unzip_cx
```

### Non-interactive
```bash
python -m unzip_cx --input /path/to/downloads --output /path/to/extracted
```

### Common options
```bash
python -m unzip_cx --input . --recursive --pattern "*.zip" --on-existing overwrite
```

## Notes
- Output folders are created using the archive filename (extension removed).
- Supported formats vary by platform but typically include: `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tbz2`, `.tar.xz`, `.txz`.
