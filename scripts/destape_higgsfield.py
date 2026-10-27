#!/usr/bin/env python3
"""Video del Destape vía la API de pago por uso de Higgsfield (Seedance 2.5).

Miroslava a cámara con la voz generada DENTRO del video (audio nativo de
Seedance: labios sincronizados, el acento se pide en el prompt). No usa
créditos de plan; cobra a la API (open.higgsfield.ai).

Credenciales: Llavero de macOS, servicio `hfgen`, cuenta `HF_CREDENTIALS`
(KEY_ID:KEY_SECRET) — las mismas de hfgen. Nunca se imprimen.

Uso:
  python3 scripts/destape_higgsfield.py --image data/intel/brand/miroslava-avatar.png \
      --prompt-file prompt.txt --duration 15 --out reports/2026/roast/video/clip.mp4
  [--audio voz.wav]   referencia de audio (timbre) opcional
  [--aspect 9:16] [--resolution 720p] [--dry-run]
"""
import argparse
import json
import mimetypes
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.higgsfield.ai"
ENDPOINT = "bytedance/seedance-2.5/reference-to-video"
USD_POR_SEG = 0.206  # precio de lista; la API aplica descuentos encima
TERMINAL = {"completed", "failed", "nsfw", "canceled"}
TIPOS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
         ".webp": "image/webp", ".wav": "audio/wav", ".mp3": "audio/mpeg",
         ".mp4": "video/mp4"}


def credenciales():
    try:
        v = subprocess.run(["security", "find-generic-password", "-s", "hfgen",
                            "-a", "HF_CREDENTIALS", "-w"], capture_output=True,
                           text=True, timeout=10).stdout.strip()
    except Exception:
        v = ""
    if ":" not in v:
        sys.exit("Falta la llave de la API en el Llavero (servicio hfgen, cuenta HF_CREDENTIALS).")
    return v


def pedir(metodo, url, cuerpo=None, creds=None, intentos=4):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    for i in range(intentos):
        req = urllib.request.Request(url, data=datos, method=metodo, headers={
            "Authorization": f"Key {creds}", "Content-Type": "application/json",
            "User-Agent": "destape/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            detalle = e.read().decode(errors="replace")[:400]
            if (e.code >= 500 or (e.code == 400 and "concurrent" in detalle.lower())) and i < intentos - 1:
                time.sleep(5 * (i + 1))
                continue
            sys.exit(f"API {e.code}: {detalle}")
        except urllib.error.URLError as e:
            if i < intentos - 1:
                time.sleep(3)
                continue
            sys.exit(f"Sin conexión con la API: {e}")


def subir(ruta, creds):
    p = Path(ruta)
    ct = TIPOS.get(p.suffix.lower()) or mimetypes.guess_type(p.name)[0]
    if not ct:
        sys.exit(f"Tipo no soportado: {p.name}")
    r = pedir("POST", f"{BASE}/files/generate-upload-url", {"content_type": ct}, creds)
    req = urllib.request.Request(r["upload_url"], data=p.read_bytes(), method="PUT",
                                 headers=r.get("upload_headers") or {"Content-Type": ct})
    with urllib.request.urlopen(req, timeout=120):
        pass
    return r["public_url"]


def urls_salida(final):
    out = []
    for k, v in (final or {}).items():
        if k in ("status_url", "cancel_url"):
            continue
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, dict) and isinstance(x.get("url"), str):
                out.append(x["url"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", action="append", required=True)
    ap.add_argument("--audio", action="append", default=[])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    ap.add_argument("--duration", type=int, default=15)
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--resolution", default="720p")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    prompt = a.prompt or Path(a.prompt_file).read_text().strip()
    if not 4 <= a.duration <= 30:
        sys.exit("Seedance 2.5: duración entre 4 y 30 s.")
    print(f"Costo de lista: {a.duration}s × ${USD_POR_SEG}/s = ${a.duration * USD_POR_SEG:.2f} (antes de descuentos)")
    cuerpo = {"prompt": prompt, "duration": a.duration, "aspect_ratio": a.aspect,
              "resolution": a.resolution, "generate_audio": True}
    if a.dry_run:
        print(f"POST {BASE}/{ENDPOINT}", json.dumps({**cuerpo, "image_urls": a.image, "audio_urls": a.audio}, ensure_ascii=False, indent=1))
        return

    creds = credenciales()
    cuerpo["image_urls"] = [subir(i, creds) for i in a.image]
    if a.audio:
        cuerpo["audio_urls"] = [subir(x, creds) for x in a.audio]
    acc = pedir("POST", f"{BASE}/{ENDPOINT}", cuerpo, creds)
    rid = acc.get("request_id")
    print(f"Solicitud {rid} — generando…", flush=True)
    estado_url = acc.get("status_url") or f"{BASE}/requests/{rid}/status"
    final, espera, t0 = acc, 3, time.time()
    while final.get("status") not in TERMINAL:
        if time.time() - t0 > 30 * 60:
            sys.exit(f"Tiempo agotado esperando {rid}")
        time.sleep(espera)
        espera = min(espera * 1.5, 15)
        final = pedir("GET", estado_url, creds=creds)
    if final["status"] != "completed":
        sys.exit(f"Terminó en {final['status']}: {final.get('error', '')}")
    urls = [u for u in urls_salida(final) if ".mp4" in u or ".mov" in u] or urls_salida(final)
    if not urls:
        sys.exit("Completado, pero sin URL de video en la respuesta.")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(urls[0], a.out)
    Path(a.out).with_suffix(".json").write_text(json.dumps(
        {"request_id": rid, "endpoint": ENDPOINT, "body": {k: v for k, v in cuerpo.items()}, "final": final},
        ensure_ascii=False, indent=1))
    print(f"Listo ({time.time() - t0:.0f}s): {a.out}")


if __name__ == "__main__":
    main()
