"""Install pinned Tesseract locally on Arch x86_64, without changing the OS."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / ".cache/ocr/tesseract"
REVISION = "e12c65a915945e4c28e237a9b52bc4a8f39a0cec"
PACKAGES = {
    "tesseract-5.5.4-1-x86_64.pkg.tar.zst": "6c33ced8c8f2b82aaeaf88a7b670b144f3c4501368477db2bb83e03a2c0cc625",
    "leptonica-1.87.0-2-x86_64.pkg.tar.zst": "f7a239ee5f8492edfd6b2e61b3c7d4371ab27990db8f10de5bbbdadc50fafb71",
}
MODELS_SHA256 = {
    "vie": "b6b49293d95d0b6dbd8780174627e82c75be957b6f4ed9862155540d6b00bb45",
    "chi_tra": "1aa60488574cafa69486d919284f079ca9b68fcc7f6ad8dc1ff1b318dfd97028",
}


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url, target, expected=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and (expected is None or checksum(target) == expected):
        return
    request = urllib.request.Request(url, headers={"User-Agent": "group1-ocr-setup"})
    temporary = target.with_suffix(target.suffix+".part")
    with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as stream:
        while chunk := response.read(1024*1024):
            stream.write(chunk)
    if expected and checksum(temporary) != expected:
        raise ValueError(f"Checksum mismatch: {target.name}")
    temporary.replace(target)


def main():
    PREFIX.mkdir(parents=True, exist_ok=True)
    for name, expected in PACKAGES.items():
        package = PREFIX / "downloads" / name
        download("https://geo.mirror.pkgbuild.com/extra/os/x86_64/"+name, package, expected)
        subprocess.run(["bsdtar", "--no-same-owner", "-xf", str(package), "-C", str(PREFIX), "usr"], check=True)
        print("Installed locally:", name, flush=True)
    models = {}
    for language in ("vie", "chi_tra"):
        target = PREFIX / "tessdata" / (language+".traineddata")
        url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/{REVISION}/{language}.traineddata"
        download(url, target, MODELS_SHA256[language])
        models[language] = {"revision": REVISION, "sha256": checksum(target)}
        print("Downloaded model:", language, flush=True)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(PREFIX / "usr/lib")+os.pathsep+env.get("LD_LIBRARY_PATH", "")
    version = subprocess.run([str(PREFIX / "usr/bin/tesseract"), "--version"], env=env,
                             capture_output=True, text=True, check=True).stdout.splitlines()[0]
    metadata = {"version": version, "packages_sha256": PACKAGES, "models": models}
    (PREFIX / "installation.json").write_text(json.dumps(metadata, indent=2)+"\n")
    print(version, "ready:", PREFIX, flush=True)


if __name__ == "__main__":
    main()
