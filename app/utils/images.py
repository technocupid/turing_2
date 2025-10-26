# app/utils/images.py
import os
import io
import json
import uuid
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from PIL import Image

# safe image extensions we allow
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def _safe_ext(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lower()

def _make_filename(original_name: str) -> str:
    ext = _safe_ext(original_name) or ".jpg"
    # name = uuid.uuid4().hex
    name = original_name[:-len(ext)]
    return f"{name}{ext}"

async def save_image_upload(upload_file, product_id: str, base_dir: str, sizes: Optional[List[Tuple[int,int]]] = None) -> Dict[str, List[str]]:
    """
    Save an UploadFile for product_id under base_dir/products/<product_id>/.
    Creates the original file and additional resized versions (sizes).
    Returns dict: {"original": "<fname>", "variants": ["<fname1>","<fname2>"]}
    - upload_file is a starlette UploadFile (async); caller should await .read()
    """
    # ensure sizes default (large, thumb)
    if sizes is None:
        sizes = [(1200, 1200), (300, 300)]  # large, thumbnail

    product_dir = Path(base_dir) / "products" / str(product_id)
    _ensure_dir(product_dir)

    # read bytes (UploadFile is async)
    contents = await upload_file.read()
    # determine extension from filename
    orig_name = upload_file.filename or "upload.jpg"
    ext = _safe_ext(orig_name)
    if ext not in ALLOWED_EXT:
        # try to detect from bytes via PIL format
        try:
            im = Image.open(io.BytesIO(contents))
            format_ext = f".{im.format.lower()}" if im.format else ".jpg"
            ext = format_ext
        except Exception:
            ext = ".jpg"

    # save original
    fname = _make_filename(orig_name)
    orig_path = product_dir / fname
    with open(orig_path, "wb") as f:
        f.write(contents)

    saved = {"original": fname, "variants": []}

    # open image with PIL and create resized variants
    try:
        im = Image.open(io.BytesIO(contents))
        im = im.convert("RGB")
        for sz in sizes:
            w, h = sz
            im_copy = im.copy()
            im_copy.thumbnail((w, h))
            vname = f"{Path(fname).stem}_{w}x{h}{Path(fname).suffix}"
            vpath = product_dir / vname
            im_copy.save(vpath, optimize=True, quality=85)
            saved["variants"].append(vname)
    except Exception:
        # if PIL fails, just skip variants
        pass

    return saved


def list_product_images(base_dir: str, product_id: str) -> List[str]:
    product_dir = Path(base_dir) / "products" / str(product_id)
    if not product_dir.exists():
        return []
    return [p.name for p in sorted(product_dir.iterdir()) if p.is_file()]

def delete_product_image(base_dir: str, product_id: str, filename: str) -> bool:
    product_dir = Path(base_dir) / "products" / str(product_id)
    path = product_dir / filename
    if path.exists():
        try:
            path.unlink()
        except Exception:
            return False
    # also try to remove variants that start with same stem
    stem = Path(filename).stem
    for p in product_dir.glob(f"{stem}*"):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    return True
