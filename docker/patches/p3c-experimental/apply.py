#!/usr/bin/env python3
"""Reproduce rejected P3c candidates in a disposable pinned checkout only.

Neither candidate meets camera acceptance. This is not used by Dockerfile.
"""

import argparse
import hashlib
from pathlib import Path
import subprocess


REVISION = "b21eb8e194c570ff2f61e91aeffb38d73dc25f42"
FILES = {
    "Library/src/graphics/OpenGLPipeline.cpp": (
        "d6d29efd823d732b4bf22d95357d2f45c8b40dfb649bf835cca548286c23a6bf",
        "23596adeeed3f8d4c5147c472eb570889167f99053ee70599fdb5b31857505b9",
    ),
    "Library/src/graphics/OpenGLRealCamera.cpp": (
        "122b959d021dbe2a28c3210672a5d467b3117e745a20495db5433c156f56631d",
        "e0f60f226d043d8224e3dedc6ede03d4fec9856bebd03cefbf45dfbfee8ecf66",
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", choices=("1", "2"))
    args = parser.parse_args()
    source = args.source.resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != REVISION:
        raise SystemExit(f"Stonefish revision mismatch: {revision}; expected {REVISION}")
    actual = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in FILES
    }
    expected = {
        name: hashes[1 if args.candidate == "2" or "Pipeline" in name else 0]
        for name, hashes in FILES.items()
    }
    if actual == expected:
        print("Experimental candidate already applied; acceptance remains FAILED.")
        return
    if actual != {name: hashes[0] for name, hashes in FILES.items()}:
        raise SystemExit("Source drift or mixed candidate state; use a fresh disposable checkout.")
    filename = ("pending-views.patch" if args.candidate == "1"
                else "pending-views-framebuffer-readback.patch")
    patch = Path(__file__).resolve().parent / filename
    command = ["git", "-C", str(source), "apply"]
    subprocess.run([*command, "--check", str(patch)], check=True)
    subprocess.run([*command, str(patch)], check=True)
    if any(hashlib.sha256((source / name).read_bytes()).hexdigest() != digest
           for name, digest in expected.items()):
        raise SystemExit("Patched-source verification failed.")
    print("Experimental candidate applied; acceptance remains FAILED.")


if __name__ == "__main__":
    main()
