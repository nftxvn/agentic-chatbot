#!/usr/bin/env python3
"""Compare the 24 before/after settings captures produced by settings-crud.js.

Use the application's Python environment (Pillow is in requirements.lock.txt).
Missing images, size changes and any changed RGB pixel fail the comparison.
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops


def compare(directory: Path, reference_prefix: str = "before", candidate_prefix: str = "after") -> dict:
    images = []
    for domain in ("directories", "fastpaths"):
        for theme in ("dark", "light"):
            for width in (1440, 1024, 390):
                for state in ("list", "modal"):
                    name = f"{domain}-{theme}-{width}-{state}.png"
                    before = directory / f"{reference_prefix}-{name}"
                    after = directory / f"{candidate_prefix}-{name}"
                    if not before.is_file() or not after.is_file():
                        images.append({"image": name, "status": "missing"})
                        continue
                    with Image.open(before) as old, Image.open(after) as new:
                        if old.size != new.size:
                            images.append({"image": name, "status": "size_changed", "before": old.size, "after": new.size})
                            continue
                        difference = ImageChops.difference(old.convert("RGB"), new.convert("RGB"))
                        changed = sum(1 for pixel in difference.get_flattened_data() if any(pixel)) if hasattr(difference, "get_flattened_data") else sum(1 for pixel in difference.getdata() if any(pixel))
                        images.append({"image": name, "status": "passed" if changed == 0 else "pixels_changed", "size": old.size, "changed_pixels": changed})
    return {"status": "passed" if all(item["status"] == "passed" for item in images) else "failed", "pairs": len(images), "images": images}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--reference-prefix", choices=["before", "after", "current"], default="before")
    parser.add_argument("--candidate-prefix", choices=["before", "after", "current"], default="after")
    args = parser.parse_args()
    result = compare(args.directory, args.reference_prefix, args.candidate_prefix)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
