#!/usr/bin/env python3
"""Deterministic Monte-Carlo reference for IC under iid uniform A-Z ciphertext.
This is a screening statistic only; it is not a complete Enigma null model.
"""
import json, random, pathlib, collections, statistics
ROOT=pathlib.Path(__file__).resolve().parent
random.seed(19410930)

def letters(s): return ''.join(c for c in s if 'A' <= c <= 'Z')
def ic(s):
    n=len(s); c=collections.Counter(s)
    return sum(v*(v-1) for v in c.values())/(n*(n-1))
def rand_ic(n):
    c=[0]*26
    for _ in range(n): c[random.randrange(26)]+=1
    return sum(v*(v-1) for v in c)/(n*(n-1))

corpus=json.loads((ROOT/'corpus.json').read_text())
TRIALS=100000
for m in corpus['messages']:
    s=letters(m['ciphertext']); obs=ic(s)
    vals=[rand_ic(len(s)) for _ in range(TRIALS)]
    mean=statistics.fmean(vals); sd=statistics.pstdev(vals)
    ge=sum(v>=obs for v in vals)/TRIALS
    le=sum(v<=obs for v in vals)/TRIALS
    print(f"{m['designator']} n={len(s)} obs={obs:.6f} null_mean={mean:.6f} z={(obs-mean)/sd:.2f} P(IC>=obs)={ge:.6g} P(IC<=obs)={le:.6g}")
