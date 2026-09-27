#!/usr/bin/env python3
import json, math, collections
from resources import resource_root

ROOT = resource_root()

def letters_only(s):
    return ''.join(c for c in s if 'A' <= c <= 'Z')

def ic(s):
    s = letters_only(s)
    n = len(s)
    counts = collections.Counter(s)
    return sum(v*(v-1) for v in counts.values()) / (n*(n-1)) if n > 1 else 0.0

def entropy(s):
    s = letters_only(s)
    n = len(s)
    counts = collections.Counter(s)
    return -sum((v/n)*math.log2(v/n) for v in counts.values())

def repeated_ngrams(s, n=3):
    s = s.upper()
    grams = collections.Counter(
        s[i:i+n] for i in range(len(s)-n+1)
        if all('A' <= c <= 'Z' for c in s[i:i+n])
    )
    return [(g,c) for g,c in grams.most_common() if c > 1]

def autocorrelation(s, max_shift=30):
    s = s.upper()
    out=[]
    for k in range(1,min(max_shift,len(s)-1)+1):
        pairs = [(a, b) for a, b in zip(s[:-k], s[k:])
                 if 'A' <= a <= 'Z' and 'A' <= b <= 'Z']
        m=sum(a==b for a,b in pairs)
        out.append((k,m,m/len(pairs) if pairs else 0.0))
    return sorted(out,key=lambda x:x[2],reverse=True)

def main():
    corpus=json.loads((ROOT/'corpus.json').read_text())
    print('designator,date,n_known,IC,entropy_bits')
    for m in corpus['messages']:
        s=m['ciphertext']
        print(f"{m['designator']},{m['date']},{len(letters_only(s))},{ic(s):.6f},{entropy(s):.4f}")
        print('  repeats:', repeated_ngrams(s,3)[:10])
        print('  autocorr:', autocorrelation(s,30)[:5])


if __name__ == '__main__':
    main()
