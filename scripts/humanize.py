#!/usr/bin/env python3
"""Portable image post-processing; source files are never edited."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from check_deps import check

PROFILES = {
    "light": dict(noise=1.5, contrast=1.03, saturation=1.01, brightness=1.02,
                  blur=.2, sharpen=.5, resize=.99, quality_low=88, quality_high=96),
    "medium": dict(noise=2.5, contrast=1.05, saturation=1.03, brightness=1.03,
                   blur=.3, sharpen=.8, resize=.97, quality_low=80, quality_high=94),
    "heavy": dict(noise=4., contrast=1.08, saturation=1.05, brightness=1.04,
                  blur=.5, sharpen=1.2, resize=.95, quality_low=72, quality_high=92),
}
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def digest(path):
    with path.open("rb") as stream:
        return sha256(stream.read()).hexdigest()


def same_file(a, b):
    if a.resolve() == b.resolve():
        return True
    return a.exists() and b.exists() and os.path.samefile(a, b)


def inside(path, directory):
    return path.resolve().is_relative_to(directory.resolve())


def publish(data, target, overwrite):
    """Stage on the same volume; do not truncate existing files on failure."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".humanize-", dir=target.parent) as directory:
        staged = Path(directory) / "output"
        staged.write_bytes(data)
        if overwrite:
            os.replace(staged, target)
        else:
            # Prefer atomic publication. FAT/exFAT use exclusive creation instead.
            try:
                os.link(staged, target)
            except FileExistsError:
                raise ValueError(f"Output exists; use another path or --overwrite: {target}")
            except OSError:
                with target.open("xb") as output:
                    try:
                        with staged.open("rb") as source:
                            shutil.copyfileobj(source, output)
                    except BaseException:
                        output.close()
                        target.unlink(missing_ok=True)
                        raise


def pick_format(output, requested, transparent):
    suffix = output.suffix.lower() if output else ""
    suffix_format = {".jpg": "jpg", ".jpeg": "jpg", ".png": "png"}.get(suffix)
    if output and not suffix_format:
        raise ValueError("Output file extension must be .jpg, .jpeg or .png")
    if requested != "auto":
        if suffix_format and suffix_format != requested:
            raise ValueError("--format conflicts with the output file extension")
        return requested
    return suffix_format or ("png" if transparent else "jpg")


def transform(source, destination, args):
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    import numpy as np

    input_hash = digest(source)
    with Image.open(source) as original:
        if getattr(original, "n_frames", 1) != 1:
            raise ValueError("Animated or multipage images are not supported")
        image = ImageOps.exif_transpose(original)
        image.load()
        transparent = "A" in image.getbands() or "transparency" in image.info
        rgba = image.convert("RGBA") if transparent else None
        rgb = image.convert("RGB")
    fmt = pick_format(destination, args.format, transparent)
    destination = destination or source.with_name(f"{source.stem}_humanized.{fmt}")
    if same_file(source, destination):
        raise ValueError("Output must not overwrite the source image (including links)")
    if destination.exists() and not args.overwrite:
        raise ValueError(f"Output exists; use another path or --overwrite: {destination}")
    alpha = None
    if rgba is not None:
        if fmt == "jpg":
            background = Image.new("RGBA", rgba.size, args.background)
            rgb = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            alpha = rgba.getchannel("A")
            rgb = rgba.convert("RGB")
    profile = PROFILES[args.strength]
    if not args.metadata_only:
        array = np.array(rgb, dtype=np.float32)
        rng = np.random.default_rng(args.seed)
        array = np.clip(array + rng.normal(0, profile["noise"], array.shape), 0, 255)
        rgb = Image.fromarray(array.astype(np.uint8))
        rgb = ImageEnhance.Contrast(rgb).enhance(profile["contrast"])
        rgb = ImageEnhance.Color(rgb).enhance(profile["saturation"])
        rgb = ImageEnhance.Brightness(rgb).enhance(profile["brightness"])
        rgb = rgb.filter(ImageFilter.GaussianBlur(profile["blur"]))
        rgb = rgb.filter(ImageFilter.UnsharpMask(radius=profile["sharpen"],
                                               percent=120, threshold=3))
        size = rgb.size
        smaller = tuple(max(1, int(value * profile["resize"])) for value in size)
        rgb = rgb.resize(smaller, Image.Resampling.LANCZOS).resize(
            size, Image.Resampling.LANCZOS
        )
        if fmt == "jpg":
            with BytesIO() as compressed:
                rgb.save(compressed, format="JPEG", quality=profile["quality_low"])
                compressed.seek(0)
                with Image.open(compressed) as reloaded:
                    rgb = reloaded.copy()
    if alpha is not None:
        rgb.putalpha(alpha)
    # New pixel container has no inherited EXIF, XMP, ICC or text chunks.
    clean = Image.frombytes(rgb.mode, rgb.size, rgb.tobytes())
    with BytesIO() as output:
        options = {"quality": profile["quality_high"], "optimize": True} if fmt == "jpg" else {}
        clean.save(output, format="JPEG" if fmt == "jpg" else "PNG", **options)
        content = output.getvalue()
    with Image.open(BytesIO(content)) as validation:
        validation.verify()
    if digest(source) != input_hash:
        raise ValueError("Source changed during processing; output was not published")
    publish(content, destination, args.overwrite)
    return {
        "input": str(source), "output": str(destination), "status": "success",
        "input_sha256": input_hash, "output_sha256": sha256(content).hexdigest(),
        "size": list(clean.size), "format": fmt, "alpha_preserved": alpha is not None,
        "mode": "metadata-only" if args.metadata_only else args.strength,
        "seed": args.seed, "parameters": {} if args.metadata_only else profile,
    }


def parser():
    cli = argparse.ArgumentParser(description="Image texture post-processing; preserves sources.")
    cli.add_argument("input", type=Path)
    cli.add_argument("-o", "--output", type=Path)
    cli.add_argument("--strength", choices=PROFILES, default="medium")
    cli.add_argument("--format", choices=["auto", "jpg", "png"], default="auto")
    cli.add_argument("--background", default="#FFFFFF")
    cli.add_argument("--seed", type=int)
    cli.add_argument("--metadata-only", "--no-metadata", action="store_true")
    cli.add_argument("--batch", action="store_true")
    cli.add_argument("--recursive", action="store_true")
    cli.add_argument("--overwrite", action="store_true")
    cli.add_argument("--report", type=Path)
    cli.add_argument("-q", "--quiet", action="store_true")
    return cli


def main():
    cli = parser()
    args = cli.parse_args()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", args.background):
        cli.error("--background must be #RRGGBB")
    if args.seed is not None and args.seed < 0:
        cli.error("--seed must be nonnegative")
    if args.recursive and not args.batch:
        cli.error("--recursive requires --batch")
    deps = check()
    if not all(item["ok"] for item in deps.values()):
        print("Missing/incompatible dependencies. Run scripts/check_deps.py with this Python.",
              file=sys.stderr)
        return 3
    source = args.input.resolve()
    if not source.exists():
        print(f"Input does not exist: {source}", file=sys.stderr)
        return 1
    if args.batch:
        if not source.is_dir():
            cli.error("--batch requires a directory")
        out_dir = (args.output or source / "humanized_output").resolve()
        if out_dir == source or inside(source, out_dir):
            cli.error("Batch output must not be the input directory or its ancestor")
        candidates = source.rglob("*") if args.recursive else source.iterdir()
        inputs = sorted(path for path in candidates if path.is_file()
                        and not path.is_symlink() and path.suffix.lower() in EXTENSIONS
                        and not inside(path, out_dir)
                        and not inside(path, source / "humanized_output"))
        if not inputs:
            print("No supported images found.", file=sys.stderr)
            return 1
    else:
        if not source.is_file():
            cli.error("Directory input requires --batch")
        inputs = [source]
        out_dir = None
    jobs = []
    for item in inputs:
        if args.batch:
            # Keep the source extension to avoid same-stem .jpg/.png collisions.
            from PIL import Image
            try:
                with Image.open(item) as image:
                    alpha = "A" in image.getbands() or "transparency" in image.info
                fmt = pick_format(None, args.format, alpha)
            except Exception:
                fmt = "jpg"
            relative = item.relative_to(source)
            destination = out_dir / relative.parent / f"{item.name}_humanized.{fmt}"
        else:
            destination = args.output.resolve() if args.output else None
        jobs.append((item, destination))
    report = args.report.resolve() if args.report else None
    if report:
        protected = inputs + [dest for _, dest in jobs if dest is not None]
        if args.batch and inside(report, source) and not inside(report, out_dir):
            cli.error("Report must not be written into the input tree")
        if any(same_file(report, path) for path in protected):
            cli.error("Report must not overwrite an input or output image")
        if report.suffix.lower() != ".json":
            cli.error("Report extension must be .json")
        if report.exists() and not args.overwrite:
            print(f"Report already exists: {report}", file=sys.stderr)
            return 1
    results = []
    for item, destination in jobs:
        try:
            result = transform(item, destination, args)
            if not args.quiet:
                print(f"OK: {result['output']}")
        except Exception as exc:
            result = {"input": str(item), "status": "failed", "error": str(exc)}
            print(f"FAILED: {item}: {exc}", file=sys.stderr)
        results.append(result)
    failures = sum(item["status"] == "failed" for item in results)
    summary = {"skill": "image-humanize", "success": len(results) - failures,
               "failed": failures, "results": results}
    if report:
        try:
            publish(json.dumps(summary, ensure_ascii=True, indent=2).encode("utf-8"),
                    report, args.overwrite)
        except Exception as exc:
            print(f"Report failed: {exc}", file=sys.stderr)
            return 1
    if not args.quiet:
        print(f"Summary: {summary['success']} succeeded, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
