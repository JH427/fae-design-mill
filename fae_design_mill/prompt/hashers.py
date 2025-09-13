from __future__ import annotations
import hashlib
import math
import random
from typing import Iterable, List, Sequence, Tuple


def _tokenize(text: str) -> List[str]:
    # Simple alnum tokens + key separators
    out: List[str] = []
    buf = []
    for ch in text:
        if ch.isalnum():
            buf.append(ch.lower())
        else:
            if buf:
                out.append("".join(buf))
                buf = []
            if ch in ":,{}[]":
                out.append(ch)
    if buf:
        out.append("".join(buf))
    return out


def simhash64(text: str) -> str:
    # Classic SimHash over tokens
    tokens = _tokenize(text)
    v = [0] * 64
    for tok in tokens:
        h = int.from_bytes(hashlib.sha1(tok.encode("utf-8")).digest()[:8], "big")
        for i in range(64):
            v[i] += 1 if ((h >> i) & 1) else -1
    out = 0
    for i in range(64):
        if v[i] > 0:
            out |= (1 << i)
    return f"{out:016x}"


def shingles(text: str, k: int = 5) -> List[int]:
    # Byte-level k-grams hashed to ints
    b = text.encode("utf-8")
    out: List[int] = []
    for i in range(0, max(0, len(b) - k + 1)):
        out.append(int.from_bytes(hashlib.sha1(b[i:i+k]).digest()[:8], "big"))
    return out


def minhash(text: str, num_perm: int = 64) -> List[int]:
    # Simple MinHash with random a,b per permutation over 64-bit universe
    sh = shingles(text, 5)
    if not sh:
        return [0] * num_perm
    random.seed(42)
    perms = [(random.randrange(1, 2**61-1), random.randrange(0, 2**61-1)) for _ in range(num_perm)]
    m = 2**61 - 1
    sig = [2**63-1] * num_perm
    for x in sh:
        for i, (a, b) in enumerate(perms):
            v = (a * x + b) % m
            if v < sig[i]:
                sig[i] = v
    return sig


def minhash_hex(text: str, num_perm: int = 64) -> str:
    sig = minhash(text, num_perm)
    # hex-encode as concatenated 8-byte hex blocks
    return "".join(f"{x:016x}" for x in sig)


def hamming_distance_hex(a_hex: str, b_hex: str, bits: int = 64) -> int:
    try:
        a = int(a_hex, 16)
        b = int(b_hex, 16)
        return (a ^ b).bit_count()
    except Exception:
        return 64


def minhash_similarity_hex(a_hex: str, b_hex: str) -> float:
    """Approximate Jaccard similarity from two hex-encoded MinHash signatures.

    Signatures are concatenations of 64-bit hex numbers (16 hex chars each).
    """
    if not a_hex or not b_hex:
        return 0.0
    chunk = 16
    n = min(len(a_hex), len(b_hex)) // chunk
    if n == 0:
        return 0.0
    eq = 0
    for i in range(n):
        if a_hex[i*chunk:(i+1)*chunk] == b_hex[i*chunk:(i+1)*chunk]:
            eq += 1
    return eq / n


def dhash_gray(image: List[List[int]]) -> str:
    # image: 2D grayscale 0..255
    # Downscale to 9x8 by sampling
    h = len(image)
    w = len(image[0]) if h else 0
    if w < 9 or h < 8:
        # naive pad by repeating last row/col
        image = _resize_nn(image, 9, 8)
    small = _resize_nn(image, 9, 8)
    # compute differences row-wise
    bits = 0
    idx = 0
    for y in range(8):
        for x in range(8):
            left = small[y][x]
            right = small[y][x+1]
            if left > right:
                bits |= (1 << idx)
            idx += 1
    return f"{bits:016x}"


def phash_gray(image: List[List[int]]) -> str:
    # pHash via DCT on 32x32 -> take top-left 8x8 (excluding DC)
    small = _resize_nn(image, 32, 32)
    dct = _dct2(small)
    vals = []
    for y in range(8):
        for x in range(8):
            if x == 0 and y == 0:
                continue
            vals.append(dct[y][x])
    avg = sum(vals) / len(vals) if vals else 0.0
    bits = 0
    for i, v in enumerate(vals[:64]):
        if v > avg:
            bits |= (1 << i)
    return f"{bits:016x}"


def _resize_nn(image: List[List[int]], new_w: int, new_h: int) -> List[List[int]]:
    h = len(image)
    w = len(image[0]) if h else 0
    if w == 0 or h == 0:
        return [[0]*new_w for _ in range(new_h)]
    out: List[List[int]] = []
    for y in range(new_h):
        src_y = min(h-1, int(y * h / new_h))
        row: List[int] = []
        for x in range(new_w):
            src_x = min(w-1, int(x * w / new_w))
            row.append(image[src_y][src_x])
        out.append(row)
    return out


def _dct2(image: List[List[int]]) -> List[List[float]]:
    # 2D DCT type-II with orthogonal normalization
    N = len(image)
    M = len(image[0]) if N else 0
    out = [[0.0]*M for _ in range(N)]
    for u in range(N):
        for v in range(M):
            sumv = 0.0
            for x in range(N):
                for y in range(M):
                    sumv += image[x][y] * math.cos(((2*x+1)*u*math.pi)/(2*N)) * math.cos(((2*y+1)*v*math.pi)/(2*M))
            cu = math.sqrt(1/N) if u == 0 else math.sqrt(2/N)
            cv = math.sqrt(1/M) if v == 0 else math.sqrt(2/M)
            out[u][v] = cu * cv * sumv
    return out
