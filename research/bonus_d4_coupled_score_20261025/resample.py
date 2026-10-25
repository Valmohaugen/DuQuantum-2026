"""Exact joint-shot coupling reduces Monte Carlo error without changing marginals."""
import json
import math
from pathlib import Path
import time

import numpy as np
from .score import from_counts

ROOT=Path(__file__).parent
MODELS=('nominal','coherent','zz','signed_zz')
REPLICATES=65536
SHOTS=10000


def coupling(p,q):
    p,q=np.asarray(p),np.asarray(q)
    shared=np.minimum(p,q)
    left,right=p-shared,q-shared
    mass=float(left.sum())
    joint=np.diag(shared)
    if mass>1e-16:
        joint+=np.outer(left,right)/mass
    joint/=joint.sum()
    error=max(float(np.max(abs(joint.sum(axis=1)-p))),
              float(np.max(abs(joint.sum(axis=0)-q))))
    assert error<1e-14 and np.min(joint)>=0
    return joint,error


def counts(p,q,rng,size):
    joint,error=coupling(p,q)
    drawn=rng.multinomial(SHOTS,joint.ravel(),size=size).reshape(size,len(p),len(q))
    return drawn.sum(axis=2),drawn.sum(axis=1),error


def sufficient(row):
    weight=np.array([i.bit_count() for i in range(16)])
    pz,px=np.array(row['pz']),np.array(row['px'])
    good=pz[weight==2]
    z=np.r_[good,max(0.,1-good.sum())];z/=z.sum()
    x=np.bincount(weight,weights=px,minlength=5);x/=x.sum()
    return z,x


def summarize(rows,cohort):
    output=[]
    for model in MODELS:
        selected=[r for r in rows if r['model']==model and
                  (cohort=='pooled' or r['cohort']==cohort)]
        if not selected:
            continue
        delta=np.array([r['delta'] for r in selected])
        base=sum(r['baseline_E_score'] for r in selected)
        output.append(dict(model=model,seeds=len(selected),mean_delta=float(delta.mean()),
                    calibration_seed_standard_error=float(delta.std(ddof=1)/math.sqrt(len(delta))),
                    MC_standard_error_of_mean=math.sqrt(sum(r['paired_MC_standard_error']**2 for r in selected))/len(selected),
                    baseline_total=base,candidate_total=base+float(delta.sum()),
                    relative_total_delta=float(delta.sum()/base),
                    negative_estimated_deltas=int(sum(delta<0)),
                    negative_beyond_two_MC_standard_errors=sum(r['delta'] < -2*r['paired_MC_standard_error'] for r in selected)))
    return output


def main():
    # Equal and disjoint distributions check the two boundary couplings.
    a,b,e=counts([.2,.3,.5],[.2,.3,.5],np.random.default_rng(839999),256)
    assert np.array_equal(a,b) and np.all(a.sum(axis=1)==SHOTS)
    joint,e2=coupling([1.,0.],[0.,1.]);assert joint[0,1]==1
    rows=[];start=time.monotonic();planned=[]
    for cohort,file in [('pilot','pilot_results.json'),('confirmation','confirmation_results.json')]:
        source=json.loads((ROOT/file).read_text())
        lookup={(r['seed'],r['model'],r['variant']):r for r in source['rows']}
        for seed in source['seeds']:
            for index,model in enumerate(MODELS):
                planned.append(dict(cohort=cohort,seed=seed,model=model))
    expired=False
    for request in planned:
        if time.monotonic()-start>75:
            expired=True;break
        cohort,seed,model=request['cohort'],request['seed'],request['model']
        source=json.loads((ROOT/(cohort+'_results.json')).read_text())
        lookup={(r['seed'],r['model'],r['variant']):r for r in source['rows']}
        base=lookup[seed,model,'baseline'];new=lookup[seed,model,'candidate']
        z0,x0=sufficient(base);z1,x1=sufficient(new)
        rng=np.random.default_rng(840000+seed*4+MODELS.index(model))
        zc0,zc1,ez=counts(z0,z1,rng,REPLICATES)
        xc0,xc1,ex=counts(x0,x1,rng,REPLICATES)
        s0=from_counts(zc0[:,:-1],xc0,4,2,SHOTS,4)[0]
        s1=from_counts(zc1[:,:-1],xc1,4,2,SHOTS,4)[0]
        assert np.isfinite(s0).all() and np.isfinite(s1).all()
        delta=s1-s0
        row=dict(**request,baseline_E_score=float(s0.mean()),candidate_E_score=float(s1.mean()),
                 delta=float(delta.mean()),paired_MC_standard_error=float(delta.std(ddof=1)/math.sqrt(len(delta))),
                 marginal_probability_error=max(ez,ex),repetitions=REPLICATES,
                 prior_delta=new['E_score']-base['E_score'])
        rows.append(row)
        if len(rows)%16==0:
            print('PROGRESS',len(rows),round(time.monotonic()-start,2),flush=True)
    result=dict(status='Exact coupled finite-shot resampling of frozen distributions',
                rows=rows,complete=not expired,planned_pairs=len(planned),completed_pairs=len(rows),
                unfinished=planned[len(rows):],seconds=time.monotonic()-start,budget_seconds=75,
                pilot=summarize(rows,'pilot'),confirmation=summarize(rows,'confirmation'),pooled=summarize(rows,'pooled'),
                identity_coupling_pass=True,disjoint_coupling_pass=True,
                method='For each basis, sample a joint multinomial with diagonal min(p,q) and residual outer product divided by total variation. Row/column sums equal the original distributions exactly; independent Z and X draws retain each circuit\'s original score law. Only estimator covariance changes.',
                limitations='Frozen synthetic distributions and four detuning realizations per model. No new circuits, noise draws, calibrations, selector tuning or measured hardware data. Per-seed negative Monte Carlo estimates are distinguished from negatives exceeding2MCstandarderrors. Across-calibration and Monte Carlo uncertainty remain separate.')
    (ROOT/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('COMPLETE',len(rows),result['seconds'],flush=True)
    print(json.dumps(result['confirmation'],indent=2),flush=True)


if __name__=='__main__':
    main()
