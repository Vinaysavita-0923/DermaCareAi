"""Download every training source for the skin gate into ./data.

  data/lfw_home/lfw_funneled/   LFW face photos (via scikit-learn)
  data/skin/scin/               450 SCIN phone photos of skin conditions
  data/skin/dermnet/            ~280 clinical close-ups across all categories
  data/hf_test/cifar10_test.parquet      CIFAR-10 test split (objects/animals)
  data/notskin/imagenette.parquet        Imagenette 320px test split (photos)
  data/notskin/cartoon/         500 cartoon illustrations

All from the Hugging Face CDN except LFW. Images are only downloaded and
later decoded with PIL; no code from any dataset is executed (script-based
dataset loaders are deliberately avoided). Seeds are fixed, so a re-run
fetches the same sample.
"""
from __future__ import annotations

import json
import random
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
HF = "https://huggingface.co"
ROWS = "https://datasets-server.huggingface.co/rows?dataset={r}&config=default&split=train&offset={o}&length=100"


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.load(r)


def download(job) -> bool:
    url, dest = job
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=300) as r:
            dest.write_bytes(r.read())
        return True
    except Exception as exc:  # one bad file shouldn't stop the run
        print("  skip", dest.name, exc.__class__.__name__, flush=True)
        return False


def fetch_all(jobs) -> int:
    with ThreadPoolExecutor(max_workers=16) as pool:
        return sum(pool.map(download, jobs))


def repo_images(repo: str) -> list[str]:
    return [s["rfilename"] for s in get_json(f"{HF}/api/datasets/{repo}")["siblings"]
            if s["rfilename"].lower().endswith((".png", ".jpg", ".jpeg"))]


def resolve(repo: str, path: str) -> str:
    return f"{HF}/datasets/{repo}/resolve/main/{urllib.parse.quote(path)}"


def main():
    from sklearn.datasets import fetch_lfw_people

    print("LFW ...", flush=True)
    fetch_lfw_people(min_faces_per_person=0, data_home=str(DATA), download_if_missing=True)

    rng = random.Random(7)
    repo = "HawkFranklin-Research/SCIN-Dermatology-Raw-Images"  # MIT
    pick = rng.sample(repo_images(repo), 450)
    jobs = [(resolve(repo, f), DATA / "skin" / "scin" / f"{i:04d}{Path(f).suffix.lower()}")
            for i, f in enumerate(pick)]
    print(f"SCIN: {fetch_all(jobs)} / {len(jobs)}", flush=True)

    repo = "raghad-murad/clinical-skin-disease"  # Apache-2.0
    by_cat: dict[str, list[str]] = {}
    for f in repo_images(repo):
        by_cat.setdefault(str(Path(f).parent), []).append(f)
    per = max(1, 300 // len(by_cat))
    pick = [f for fs in by_cat.values() for f in rng.sample(fs, min(per, len(fs)))][:300]
    jobs = [(resolve(repo, f), DATA / "skin" / "dermnet" / f"{i:04d}{Path(f).suffix.lower()}")
            for i, f in enumerate(pick)]
    print(f"DermNet: {fetch_all(jobs)} / {len(jobs)}", flush=True)

    fetch_all([
        (resolve("uoft-cs/cifar10", "plain_text/test-00000-of-00001.parquet"),
         DATA / "hf_test" / "cifar10_test.parquet"),
        (resolve("leandrodevai/imagenette-320px-resplit", "320px/test-00000-of-00001.parquet"),  # Apache-2.0
         DATA / "notskin" / "imagenette.parquet"),
    ])
    print("CIFAR-10 + Imagenette parquet done", flush=True)

    repo = "anokimchen/Cartoon_illustrations_i2i_1024x1024"  # Apache-2.0
    rng = random.Random(11)
    jobs = []
    for off in rng.sample(range(0, 28084 - 100, 100), 10):
        rows = get_json(ROWS.format(r=repo, o=off))["rows"]
        for row in rng.sample(rows, min(50, len(rows))):
            src = (row["row"].get("image") or {}).get("src")
            if src:
                jobs.append((src, DATA / "notskin" / "cartoon" / f"{off:05d}_{row['row_idx']}.png"))
    print(f"Cartoons: {fetch_all(jobs)} / {len(jobs)}", flush=True)


if __name__ == "__main__":
    main()
