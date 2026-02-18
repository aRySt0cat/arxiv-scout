#!/usr/bin/env python3
"""Download arXiv LaTeX source and extract figures."""

import gzip
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PAPERS_DIR = SCRIPT_DIR / "papers"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg", ".gif", ".bmp", ".tiff"}
MAX_FIGURES = 10  # Save at most this many figures


def convert_pdf_to_png(pdf_path: Path, png_path: Path, dpi: int = 150) -> bool:
    """Convert a single-page PDF to PNG using pdftoppm."""
    try:
        # pdftoppm outputs {prefix}-{page}.png, we use -singlefile for just one page
        prefix = str(png_path.with_suffix(""))
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), "-singlefile", str(pdf_path), prefix],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return png_path.exists()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def download_source(arxiv_id: str) -> bytes:
    """Download arXiv e-print source."""
    url = f"https://arxiv.org/e-print/{arxiv_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "arxiv-scout/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception as e:
            if attempt == 2:
                raise
            wait = 5 * (attempt + 1)
            print(f"  Attempt {attempt + 1} failed ({e}), retrying in {wait}s ...")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def extract_tar(data: bytes, dest: Path) -> None:
    """Extract a (possibly gzipped) tar archive."""
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            tar.extractall(dest, filter="data")
            return
    except (tarfile.TarError, gzip.BadGzipFile):
        pass

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
            tar.extractall(dest, filter="data")
            return
    except tarfile.TarError:
        pass

    # Maybe it's a single gzipped .tex file
    try:
        decompressed = gzip.decompress(data)
        (dest / "main.tex").write_bytes(decompressed)
        return
    except gzip.BadGzipFile:
        pass

    # Raw file (PDF or single tex)
    if data[:5] == b"%PDF-":
        (dest / "paper.pdf").write_bytes(data)
    else:
        (dest / "main.tex").write_bytes(data)


def find_main_tex(src_dir: Path) -> Path | None:
    """Find the main .tex file (the one containing \\documentclass)."""
    for f in src_dir.rglob("*.tex"):
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"\\documentclass", content):
                return f
        except Exception:
            continue
    return None


def resolve_tex_content(tex_path: Path, src_dir: Path, visited: set[str] | None = None) -> str:
    """Recursively resolve \\input/\\include directives to build full document in order."""
    if visited is None:
        visited = set()

    resolved = str(tex_path.resolve())
    if resolved in visited:
        return ""
    visited.add(resolved)

    try:
        content = tex_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    input_pattern = re.compile(r"\\(?:input|include)\{([^}]+)\}")

    result = []
    last_end = 0
    for match in input_pattern.finditer(content):
        result.append(content[last_end:match.start()])
        ref = match.group(1)
        # Resolve the referenced file
        child = _find_tex_file(ref, tex_path.parent, src_dir)
        if child and child.exists():
            result.append(resolve_tex_content(child, src_dir, visited))
        last_end = match.end()
    result.append(content[last_end:])
    return "".join(result)


def _find_tex_file(ref: str, parent_dir: Path, src_dir: Path) -> Path | None:
    """Find a .tex file from an \\input reference, trying with and without .tex extension."""
    candidates = [
        parent_dir / ref,
        parent_dir / (ref + ".tex"),
        src_dir / ref,
        src_dir / (ref + ".tex"),
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def find_image_files(src_dir: Path) -> dict[str, Path]:
    """Find all image files, keyed by stem (relative path without extension)."""
    images: dict[str, Path] = {}
    for f in src_dir.rglob("*"):
        if f.suffix.lower() in IMAGE_EXTENSIONS and f.is_file():
            rel = f.relative_to(src_dir)
            key = str(rel.with_suffix("")).replace("\\", "/")
            images[key] = f
    return images


def parse_figures_from_tex(tex_content: str) -> list[dict]:
    """Parse \\begin{figure} environments to find figure numbers and their image paths."""
    figures = []
    fig_num = 0

    fig_pattern = re.compile(
        r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}",
        re.DOTALL,
    )

    for match in fig_pattern.finditer(tex_content):
        fig_num += 1
        body = match.group(1)

        # Find includegraphics paths
        img_pattern = re.compile(r"\\includegraphics(?:\[.*?\])?\{([^}]+)\}")
        img_paths = img_pattern.findall(body)

        # Find caption
        cap_pattern = re.compile(r"\\caption(?:\[.*?\])?\{(.+?)\}", re.DOTALL)
        cap_match = cap_pattern.search(body)
        caption = cap_match.group(1).strip() if cap_match else ""
        # Clean up LaTeX commands in caption
        caption = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", caption)
        caption = re.sub(r"[{}]", "", caption)
        caption = " ".join(caption.split())
        if len(caption) > 120:
            caption = caption[:117] + "..."

        figures.append({
            "number": fig_num,
            "image_paths": img_paths,
            "caption": caption,
        })

    return figures


def resolve_image(img_ref: str, images: dict[str, Path]) -> Path | None:
    """Resolve a LaTeX image reference to an actual file."""
    # Try exact match first
    if img_ref in images:
        return images[img_ref]

    # Strip leading ./
    clean = img_ref.lstrip("./")
    if clean in images:
        return images[clean]

    # Try with common extensions
    for ext in [".png", ".pdf", ".jpg", ".jpeg", ".eps", ".svg"]:
        key = clean + ext if not clean.endswith(ext) else clean
        key_no_ext = key.rsplit(".", 1)[0] if "." in key else key
        if key_no_ext in images:
            return images[key_no_ext]

    # Basename match
    base = os.path.basename(clean)
    base_no_ext = base.rsplit(".", 1)[0] if "." in base else base
    for key, path in images.items():
        if os.path.basename(key) == base_no_ext:
            return path

    return None


def extract_figures(arxiv_id: str, published_date: str, output_base: Path | None = None) -> dict:
    """
    Download arXiv source, extract figures, return info.

    Returns dict with:
        - tex_content: str (concatenated .tex content)
        - figures: list of {number, caption, saved_path}
        - output_dir: Path
    """
    if output_base is None:
        output_base = PAPERS_DIR

    # Build output directory: papers/yyyy-mm-dd/{id}/
    clean_id = arxiv_id.replace(".", "").replace("/", "")
    out_dir = output_base / published_date / clean_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading source for {arxiv_id} ...")
    data = download_source(arxiv_id)
    print(f"  Downloaded {len(data)} bytes")

    # Extract to temp directory
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        extract_tar(data, tmp_path)

        # Find main tex and image files
        main_tex = find_main_tex(tmp_path)
        images = find_image_files(tmp_path)

        if main_tex:
            print(f"  Main TeX: {main_tex.relative_to(tmp_path)}")
            tex_content = resolve_tex_content(main_tex, tmp_path)
        else:
            # Fallback: concatenate all .tex files
            tex_files = sorted(tmp_path.rglob("*.tex"))
            print(f"  No main TeX found, concatenating {len(tex_files)} .tex files")
            tex_content = ""
            for tf in tex_files:
                try:
                    tex_content += tf.read_text(encoding="utf-8", errors="ignore") + "\n"
                except Exception:
                    continue

        print(f"  Found {len(images)} image files")

        # Parse figures in document order
        figures = parse_figures_from_tex(tex_content)
        print(f"  Found {len(figures)} figure environments in LaTeX")

        saved_figures = []
        for fig in figures:
            if len(saved_figures) >= MAX_FIGURES:
                print(f"  Reached max figures ({MAX_FIGURES}), stopping extraction")
                break

            for img_ref in fig["image_paths"]:
                resolved = resolve_image(img_ref, images)
                if resolved is None:
                    print(f"  WARNING: Could not resolve image: {img_ref}")
                    continue

                ext = resolved.suffix.lower()
                if ext == ".eps":
                    print(f"  Skipping EPS file: {img_ref}")
                    continue

                # Convert PDF figures to PNG for markdown embedding
                if ext == ".pdf":
                    dest_name = f"figure{fig['number']}.png"
                    dest_path = out_dir / dest_name
                    if convert_pdf_to_png(resolved, dest_path):
                        print(f"  Saved {dest_name} (converted from PDF, {dest_path.stat().st_size} bytes)")
                    else:
                        # Fallback: save as PDF
                        dest_name = f"figure{fig['number']}.pdf"
                        dest_path = out_dir / dest_name
                        shutil.copy2(resolved, dest_path)
                        print(f"  Saved {dest_name} (PDF, pdftoppm conversion failed)")
                else:
                    dest_name = f"figure{fig['number']}{ext}"
                    dest_path = out_dir / dest_name
                    shutil.copy2(resolved, dest_path)
                    print(f"  Saved {dest_name} ({resolved.stat().st_size} bytes)")

                saved_figures.append({
                    "number": fig["number"],
                    "caption": fig["caption"],
                    "filename": dest_name,
                    "saved_path": str(dest_path),
                })
                break  # Take first image per figure environment

    return {
        "tex_content": tex_content,
        "figures": saved_figures,
        "output_dir": out_dir,
        "clean_id": clean_id,
    }


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: extract_source.py <arxiv_id> <published_date>")
        print("Example: extract_source.py 2602.14486 2026-02-16")
        sys.exit(1)

    arxiv_id = sys.argv[1]
    published_date = sys.argv[2]

    result = extract_figures(arxiv_id, published_date)
    print(f"\nOutput directory: {result['output_dir']}")
    print(f"TeX content length: {len(result['tex_content'])} chars")
    print(f"Figures saved: {len(result['figures'])}")
    for fig in result["figures"]:
        print(f"  Figure {fig['number']}: {fig['filename']} - {fig['caption'][:80]}")


if __name__ == "__main__":
    main()
