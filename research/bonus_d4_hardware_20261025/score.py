"""General-k finite-shot benchmark score from exact sufficient statistics."""
import math
import numpy as np


def tables(n,k):
    comb=lambda a,b:math.comb(a,b) if 0<=b<=a else 0
    C=comb(n,k)
    table=np.array([[sum((-1)**j*comb(w,j)*comb(n-w,r-j) for j in range(r+1))/comb(n,r)
                     for w in range(n+1)] for r in range(1,n+1)])
    expected=np.array([comb(r,r//2)*comb(n-r,k-r//2)/C if r%2==0 else 0. for r in range(1,n+1)])
    return C,table,expected


def from_counts(zcounts,xweights,n,k,shots,cutoff):
    C,table,expected=tables(n,k)
    assert zcounts.shape[-1]==C and xweights.shape[-1]==n+1
    valid=zcounts.sum(axis=-1);fraction=valid/shots;mean=valid[...,None]/C
    with np.errstate(divide='ignore',invalid='ignore'):
        zpen=((zcounts-mean)**2/mean).sum(axis=-1)/C/fraction
        averages=xweights@table.T/shots
        xterms=(averages-expected)**2/np.where(expected==0,1.,expected**2)
        xpen=xterms[...,:cutoff].sum(axis=-1)
        score=1/(zpen+xpen)
    return score,zpen,xpen


def samples(pz,px,n,k,seed,replicates=32768,shots=10000):
    weight=np.array([i.bit_count() for i in range(2**n)])
    valid=pz[weight==k]
    zprob=np.r_[valid,max(0.,1-valid.sum())];zprob/=zprob.sum()
    xp=np.bincount(weight,weights=px,minlength=n+1);xp/=xp.sum()
    rng=np.random.default_rng(seed)
    zcounts=rng.multinomial(shots,zprob,size=replicates)[:,:-1]
    xcounts=rng.multinomial(shots,xp,size=replicates)
    return {cutoff:from_counts(zcounts,xcounts,n,k,shots,cutoff)[0] for cutoff in sorted({min(4,n),n})}


def check():
    from . import judge
    rng=np.random.default_rng(752038);checks=[]
    for n,k in [(4,2),(5,2),(4,1)]:
        weights=np.array([i.bit_count() for i in range(2**n)])
        for repeat in range(4):
            zi=rng.integers(0,2**n,size=1000);xi=rng.integers(0,2**n,size=1000)
            shifts=np.arange(n-1,-1,-1)
            zb=(zi[:,None]>>shifts)&1;xb=(xi[:,None]>>shifts)&1
            zc=np.bincount(zi,minlength=2**n)[weights==k]
            xc=np.bincount(xb.sum(axis=1),minlength=n+1)
            for cutoff in sorted({min(4,n),n}):
                actual,z,x=from_counts(zc,xc,n,k,len(zi),cutoff)
                ref=judge.overall_score(zb,xb,k,cutoff)
                errors=[abs(float(actual-ref)),abs(float(z-judge.check_z_bitstring_distribution(zb,k))),abs(float(x-judge.check_x_bitstring_distribution(xb,k,cutoff)))]
                assert max(errors)<1e-12
                checks.append(dict(n=n,k=k,cutoff=cutoff,repeat=repeat,errors=errors))
    return dict(status='General-k sufficient statistics match explicit notebook bitstring scores',checks=checks,maximum_error=max(max(r['errors']) for r in checks),zero_valid_policy='Retain NaN/undefined as in judge; evaluation rejects nonfinite samples, never coerces them to zero.')
