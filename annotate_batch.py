#!/usr/bin/env python3
import os, json, requests, base64, time
from pathlib import Path
import anthropic
from PIL import Image, ImageDraw
from io import BytesIO

BATCH_SIZE = 20
VISUAL_CHECK_EVERY = 20
TAXON_ID = 52775

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def load_progress():
    p = Path("progress.json")
    if p.exists():
        return json.loads(p.read_text())
    return {"total_annotated": 0, "last_obs_id": 0, "status": "in_progress"}

def save_progress(prog):
    Path("progress.json").write_text(json.dumps(prog, indent=2))

def fetch_photos(last_obs_id, per_page=100):
    url = "https://api.inaturalist.org/v1/observations"
    params = {
        "taxon_id": TAXON_ID,
        "photo_license": "cc0",
        "photos": "true",
        "per_page": per_page,
        "order": "asc",
        "order_by": "id",
        "id_above": last_obs_id,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    photos = []
    seen = set()
    for obs in data["results"]:
        obs_id = obs["id"]
        for p in obs.get("photos", []):
            pid = p["id"]
            if pid in seen:
                continue
            seen.add(pid)
            url_large = p.get("url", "").replace("/square.", "/large.")
            photos.append({
                "obs_id": obs_id,
                "photo_id": pid,
                "taxon": obs.get("taxon", {}).get("name", "Bombus"),
                "url": url_large,
            })
    return photos

def download_image(url):
    r = requests.get(url, timeout=30)
    if len(r.content) < 5000:
        return None, None, None
    img = Image.open(BytesIO(r.content)).convert("RGB")
    return r.content, img.size[0], img.size[1]

def annotate_image(img_bytes, width, height):
    img_b64 = base64.standard_b64encode(img_bytes).decode()
    prompt = (
        f"This is a {width}x{height} image from iNaturalist tagged as Bombus (bumblebee).\n"
        "Provide YOLO bounding box annotations for every Bombus bee visible.\n"
        "Rules:\n"
        "- Include full bee: antennae, wings, body\n"
        "- Multiple bees: one line per bee\n"
        "- Format: 0 x_center y_center width height  (all values normalized 0.0-1.0)\n"
        "- If NO Bombus bee is clearly visible, respond with exactly: SKIP\n"
        "Output ONLY the YOLO lines or SKIP. No explanation."
    )
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return response.content[0].text.strip()

def save_label(stem, text):
    Path("labels").mkdir(exist_ok=True)
    Path(f"labels/{stem}.txt").write_text(text + "\n")

def save_visual_check(stem, img_bytes, label_text, width, height):
    Path("visual_check").mkdir(exist_ok=True)
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    for line in label_text.strip().splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        _, xc, yc, bw, bh = int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
        x1 = int((xc - bw / 2) * width)
        y1 = int((yc - bh / 2) * height)
        x2 = int((xc + bw / 2) * width)
        y2 = int((yc + bh / 2) * height)
        draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
    img.save(f"visual_check/{stem}.jpg")

def main():
    prog = load_progress()
    last_obs_id = prog.get("last_obs_id", 0)
    total = prog.get("total_annotated", 0)

    print(f"Starting from obs_id>{last_obs_id}, total_annotated={total}")
    photos = fetch_photos(last_obs_id)
    print(f"Fetched {len(photos)} candidate photos")

    processed = 0
    max_obs_id = last_obs_id

    for ph in photos:
        if processed >= BATCH_SIZE:
            break

        stem = f"obs{ph['obs_id']}_photo{ph['photo_id']}"
        label_path = Path(f"labels/{stem}.txt")
        if label_path.exists():
            continue

        img_bytes, w, h = download_image(ph["url"])
        if img_bytes is None:
            print(f"  SKIP (small/error): {stem}")
            continue

        try:
            result = annotate_image(img_bytes, w, h)
        except Exception as e:
            print(f"  ERROR annotating {stem}: {e}")
            continue

        if result == "SKIP":
            print(f"  SKIP (no bee): {stem}")
            max_obs_id = max(max_obs_id, ph["obs_id"])
            continue

        save_label(stem, result)
        total += 1
        processed += 1
        max_obs_id = max(max_obs_id, ph["obs_id"])

        if total % VISUAL_CHECK_EVERY == 0:
            save_visual_check(stem, img_bytes, result, w, h)

        print(f"  OK [{total}] {stem} ({ph['taxon']})")
        time.sleep(0.5)

    prog["total_annotated"] = total
    prog["last_obs_id"] = max_obs_id
    save_progress(prog)
    print(f"Batch done. Processed={processed}, total_annotated={total}, last_obs_id={max_obs_id}")

if __name__ == "__main__":
    main()
