#!/usr/bin/env python3
"""Minimal Enigma I simulator for baseline experiments.

Implements rotors I-V, reflector B, standard stepping including middle-rotor double step,
ring settings, start positions, and plugboard. This is intended as a transparent baseline,
not as the final high-performance solver.
"""
import string
A=string.ascii_uppercase
ROTOR_WIRINGS={
 'I':   ('EKMFLGDQVZNTOWYHXUSPAIBRCJ','Q'),
 'II':  ('AJDKSIRUXBLHWTMCQGZNPYFVOE','E'),
 'III': ('BDFHJLCPRTXVZNYEIWGAKMUSQO','V'),
 'IV':  ('ESOVPZJAYQUIRHXLNFTGKDCMWB','J'),
 'V':   ('VZBRGITYUPSDNHLXAWMJQOFECK','Z'),
}
REFLECTOR_B='YRUHQSLDPXNGOKMIEBFZCWVJAT'

def idx(c): return ord(c)-65
def ch(i): return chr(i%26+65)

def plugmap(pairs=''):
    m=list(range(26))
    for pair in pairs.upper().split():
        if len(pair)!=2: raise ValueError(pair)
        a,b=map(idx,pair)
        m[a],m[b]=b,a
    return m

class Rotor:
    def __init__(self,name,ring='A',pos='A'):
        wiring,notch=ROTOR_WIRINGS[name]
        self.name=name; self.w=[idx(c) for c in wiring]
        self.inv=[0]*26
        for i,v in enumerate(self.w): self.inv[v]=i
        self.notch=idx(notch); self.ring=idx(ring); self.pos=idx(pos)
    def at_notch(self): return self.pos==self.notch
    def step(self): self.pos=(self.pos+1)%26
    def fwd(self,x):
        y=(x+self.pos-self.ring)%26
        y=self.w[y]
        return (y-self.pos+self.ring)%26
    def rev(self,x):
        y=(x+self.pos-self.ring)%26
        y=self.inv[y]
        return (y-self.pos+self.ring)%26

class EnigmaI:
    def __init__(self,rotors=('I','II','III'),rings='AAA',positions='AAA',plugboard=''):
        if len(rotors)!=3 or len(rings)!=3 or len(positions)!=3: raise ValueError('3 rotors/rings/positions required')
        self.L,self.M,self.R=[Rotor(n,r,p) for n,r,p in zip(rotors,rings,positions)]
        self.plug=plugmap(plugboard)
    def step(self):
        # If middle is at notch, left steps. Middle steps if it or right is at notch.
        mid_notch=self.M.at_notch(); right_notch=self.R.at_notch()
        if mid_notch: self.L.step()
        if mid_notch or right_notch: self.M.step()
        self.R.step()
    def key(self,c):
        if c not in A: return c
        self.step(); x=self.plug[idx(c)]
        x=self.R.fwd(x); x=self.M.fwd(x); x=self.L.fwd(x)
        x=idx(REFLECTOR_B[x])
        x=self.L.rev(x); x=self.M.rev(x); x=self.R.rev(x)
        x=self.plug[x]
        return ch(x)
    def crypt(self,text): return ''.join(self.key(c) for c in text.upper() if c in A)

if __name__=='__main__':
    # Widely published standard Enigma-I vector: I-II-III, rings AAA, start AAA, no plugboard.
    # AAAAA -> BDZGO.
    v=EnigmaI(rotors=('I','II','III'),rings='AAA',positions='AAA').crypt('AAAAA')
    print('VECTOR AAAAA ->',v); assert v=='BDZGO'
    # Reciprocity sanity check: encryption and decryption are identical from the same initial state.
    p='DIESISTEINTEST'
    cfg=dict(rotors=('II','V','III'),rings='HMF',positions='RWD',plugboard='AC BE DG FH KN MO PR SU TV XZ')
    c=EnigmaI(**cfg).crypt(p)
    r=EnigmaI(**cfg).crypt(c)
    print('PT',p); print('CT',c); print('RT',r); assert r==p
