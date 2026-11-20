"""Independent Gale–Church dynamic programming with explicit null alignments.

Length units are Han characters and Vietnamese syllables. This implementation
does not import the demo aligner or treat its output as training/gold data.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .normalize import han_len, vi_len

PRIORS = {(1, 1): .89, (1, 2): .045, (2, 1): .045, (2, 2): .011,
          (1, 0): .005, (0, 1): .005, (1, 3): .01, (3, 1): .01}


@dataclass(frozen=True)
class Link:
    han_start: int
    han_end: int
    viet_start: int
    viet_end: int
    cost: float


def length_cost(han, viet, ratio, variance):
    if han == 0 and viet == 0:
        return 0.
    mean = (han + viet/ratio)/2
    z = abs(viet-ratio*han)/math.sqrt(max(mean, 1)*variance)
    return -math.log(max(math.erfc(z/math.sqrt(2)), 1e-12))


def gale_church(han_units, viet_units, ratio=2., variance=6., priors=None, anchors=(),
                unmatched_han=(), unmatched_viet=()):
    if not math.isfinite(ratio) or not math.isfinite(variance) or ratio <= 0 or variance <= 0:
        raise ValueError("Length ratio and variance must be finite and positive")
    priors = priors or PRIORS
    n, m = len(han_units), len(viet_units)
    hl, vl = [0], [0]
    for u in han_units:
        hl.append(hl[-1]+han_len(u))
    for u in viet_units:
        vl.append(vl[-1]+vi_len(u))
    costs = [[math.inf]*(m+1) for _ in range(n+1)]
    back = [[None]*(m+1) for _ in range(n+1)]
    costs[0][0] = 0.
    for i in range(n+1):
        for j in range(m+1):
            if not math.isfinite(costs[i][j]):
                continue
            for (a, b), prior in priors.items():
                if a+b < 1 or prior <= 0 or prior > 1:
                    raise ValueError("Invalid alignment transition/prior")
                ni, nj = i+a, j+b
                if ni > n or nj > m:
                    continue
                # A reliable printed verse number must be consumed on both
                # sides in the same transition. Unanchored units can still
                # use the normal one-to-many and null transitions.
                if any((i <= hi < ni) != (j <= vj < nj) for hi, vj in anchors):
                    continue
                if b and any(i <= hi < ni for hi in unmatched_han):
                    continue
                if a and any(j <= vj < nj for vj in unmatched_viet):
                    continue
                cost = -math.log(prior)+length_cost(hl[ni]-hl[i], vl[nj]-vl[j], ratio, variance)
                candidate = costs[i][j]+cost
                if candidate < costs[ni][nj]:
                    costs[ni][nj] = candidate
                    back[ni][nj] = (i, j, cost)
    links = []
    i, j = n, m
    while i or j:
        if back[i][j] is None:
            raise ValueError("Configured transitions cannot align both sequences")
        pi, pj, cost = back[i][j]
        links.append(Link(pi, i, pj, j, cost))
        i, j = pi, pj
    return list(reversed(links))


def estimate_parameters(segments):
    lengths = [(han_len(s[0]), vi_len(s[1])) for s in segments]
    lengths = [(h, v) for h, v in lengths if h >= 4 and v >= 4]
    if not lengths:
        return 2., 6.
    ratio = sum(v for h, v in lengths)/sum(h for h, v in lengths)
    variance = sum((v-ratio*h)**2/h for h, v in lengths)/len(lengths)
    return ratio, max(1., min(25., variance))
