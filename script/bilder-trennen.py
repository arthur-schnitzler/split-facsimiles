#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow"]
# ///
"""Bilder trennen: arbeitet den Ordner import/ ab und schreibt nach export/jp2/ (volle
Auflösung, mit Überlappung) und export/jpeg/ (verkleinert für Transkribus, ohne Überlappung).

Start:  ./start.sh  oder  uv run script/bilder-trennen.py   (danach http://127.0.0.1:8765 öffnen)
"""
import argparse
import io
import json
import re
import shutil
import threading
import time
import webbrowser
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
IMPORT_DIR = ROOT / "import"
EXPORT_DIR = ROOT / "export"
JP2_DIR = EXPORT_DIR / "jp2"
JPEG_DIR = EXPORT_DIR / "jpeg"
INDEX_HTML = Path(__file__).resolve().parent / "index.html"

EXTENSIONS = {".jp2", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
OVERLAP = 0.05  # Überlappung je Seite, relativ zur Bildbreite
PREVIEW_SIZE = 2400  # lange Kante der Vorschau in Pixeln
JPEG_MAX_SIZE = 2500  # Transkribus: lange Kante des JPEGs in Pixeln
JPEG_QUALITY = 85
JP2_MODES = {"L", "LA", "RGB", "RGBA", "I;16"}

Image.MAX_IMAGE_PIXELS = None

lock = threading.Lock()
keep_originals = False
server = None


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def natural_key(path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def list_files():
    files = [p for p in IMPORT_DIR.iterdir()
             if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in EXTENSIONS]
    return sorted(files, key=natural_key)


def resolve(name):
    """Dateiname aus der Anfrage nur akzeptieren, wenn er wirklich im import-Ordner liegt."""
    for p in list_files():
        if p.name == name:
            return p
    raise FileNotFoundError(name)


def load(path):
    img = Image.open(path)
    img.load()
    return ImageOps.exif_transpose(img)


def preview_jpeg(path):
    img = load(path)
    img.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE))
    if img.mode == "I;16":
        img = img.point(lambda v: v / 256).convert("L")
    if img.mode not in ("L", "RGB"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


class PreviewCache:
    def __init__(self, size=6):
        self.size, self.items = size, OrderedDict()

    def get(self, path):
        key = (path.name, path.stat().st_mtime_ns)
        if key not in self.items:
            self.items[key] = preview_jpeg(path)
            while len(self.items) > self.size:
                self.items.popitem(last=False)
        self.items.move_to_end(key)
        return self.items[key]


previews = PreviewCache()


def save_jp2(img, target, icc):
    if img.mode not in JP2_MODES:
        img = img.convert("RGBA" if "A" in img.mode else "RGB")
    tmp = target.with_name(target.name + ".part")
    kwargs = {"icc_profile": icc} if icc else {}
    img.save(tmp, "JPEG2000", **kwargs)  # ohne Qualitätsangaben: verlustfrei
    with Image.open(tmp) as check:
        check.load()
        if check.size != img.size:
            tmp.unlink()
            raise RuntimeError(f"Prüfung fehlgeschlagen: {target.name}")
    tmp.replace(target)


def save_jpeg(img, target):
    img = img.copy()
    img.thumbnail((JPEG_MAX_SIZE, JPEG_MAX_SIZE), Image.LANCZOS)
    if img.mode == "I;16":
        img = img.point(lambda v: v / 256).convert("L")
    if img.mode not in ("L", "RGB"):
        img = img.convert("RGB")
    tmp = target.with_name(target.name + ".part")
    img.save(tmp, "JPEG", quality=JPEG_QUALITY)
    tmp.replace(target)


def targets_free(paths):
    for p in paths:
        if p.exists():
            raise FileExistsError(f"export/{p.parent.name}/{p.name} existiert bereits")


def finish(src):
    if not keep_originals:
        src.unlink()


def do_move(name):
    log(f"Exportiere {name} (ohne Beschnitt) …")
    src = resolve(name)
    jp2, jpg = JP2_DIR / (src.stem + ".jp2"), JPEG_DIR / (src.stem + ".jpg")
    targets_free([jp2, jpg])
    img = load(src)
    try:
        if src.suffix.lower() == ".jp2":
            # schon JP2: unverändert kopieren (nicht neu komprimieren)
            shutil.copy2(src, jp2)
        else:
            save_jp2(img, jp2, img.info.get("icc_profile"))
        save_jpeg(img, jpg)
    except Exception:
        jp2.unlink(missing_ok=True)
        jpg.unlink(missing_ok=True)
        raise
    finish(src)
    return [jp2.name, jpg.name]


def do_split(name, x):
    if not 0.0 < x < 1.0:
        raise ValueError("Position außerhalb des Bildes")
    log(f"Trenne {name} bei {x * 100:.1f} % …")
    src = resolve(name)
    jp2s = [JP2_DIR / f"{src.stem}_{i}.jp2" for i in (0, 1)]
    jpgs = [JPEG_DIR / f"{src.stem}_{i}.jpg" for i in (0, 1)]
    targets_free(jp2s + jpgs)
    img = load(src)
    w, h = img.size
    cut, ov = round(x * w), round(OVERLAP * w)
    jp2_boxes = [(0, 0, min(w, cut + ov), h), (max(0, cut - ov), 0, w, h)]
    jpg_boxes = [(0, 0, cut, h), (cut, 0, w, h)]  # JPEG: ohne Überlappung
    icc = img.info.get("icc_profile")
    written = []
    try:
        for box, target in zip(jp2_boxes, jp2s):
            written.append(target)
            save_jp2(img.crop(box), target, icc)
        for box, target in zip(jpg_boxes, jpgs):
            written.append(target)
            save_jpeg(img.crop(box), target)
    except Exception:
        for t in written:
            t.unlink(missing_ok=True)
        raise
    finish(src)
    return [t.name for t in jp2s + jpgs]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, code, obj):
        self.send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        path, _, query = self.path.partition("?")
        try:
            if path == "/":
                self.send(200, INDEX_HTML.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/files":
                with lock:
                    self.send_json(200, {"files": [p.name for p in list_files()],
                                         "overlap": OVERLAP})
            elif path == "/api/preview":
                name = parse_qs(query).get("name", [""])[0]
                with lock:
                    data = previews.get(resolve(name))
                self.send(200, data, "image/jpeg")
            else:
                self.send(404, b"not found", "text/plain")
        except FileNotFoundError:
            self.send(404, b"not found", "text/plain")
        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/quit":
                self.send_json(200, {"ok": True})
                log("Beendet über die Oberfläche.")
                threading.Thread(target=server.shutdown, daemon=True).start()
                return
            with lock:
                if self.path == "/api/move":
                    out = do_move(body["name"])
                elif self.path == "/api/split":
                    out = do_split(body["name"], float(body["x"]))
                else:
                    return self.send(404, b"not found", "text/plain")
            log("✓ " + ", ".join(out))
            self.send_json(200, {"written": out})
        except Exception as e:
            log(f"Fehler: {e}")
            self.send_json(400, {"error": str(e)})


def main():
    global keep_originals, server
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--keep", action="store_true",
                    help="Originale in import/ behalten (Standard: nach erfolgreichem Export löschen)")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    keep_originals = args.keep
    IMPORT_DIR.mkdir(exist_ok=True)
    JP2_DIR.mkdir(parents=True, exist_ok=True)
    JPEG_DIR.mkdir(parents=True, exist_ok=True)
    url = f"http://127.0.0.1:{args.port}"
    print(f"import: {IMPORT_DIR}\nexport: {EXPORT_DIR}\n{url}  (Strg+C beendet)")
    if not args.no_browser:
        webbrowser.open(url)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
