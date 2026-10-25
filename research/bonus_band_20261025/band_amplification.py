"""State-vector proof only: exact one-step amplification of adjacent weight bands.

This is NOT a native circuit or a scored candidate. Routing and oracle synthesis
are outstanding. It checks the algebra before spending resources compiling it.
"""
import cmath
import json
import math
from pathlib import Path

import numpy as np


def main():
    rows=[]
    for n in range(2,16):
        for k in range(1,n//2+1):
            probability=math.comb(n,k)/2**(n-1)
            if probability<.25:continue
            phase=math.acos(1-1/(2*probability))
            factor=cmath.exp(1j*phase)
            initial=np.ones(2**(n-1),dtype=complex)/math.sqrt(2**(n-1))
            weights=np.array([i.bit_count() for i in range(len(initial))])
            marked=(weights==k-1)|(weights==k)
            state=initial.copy();state[marked]*=factor
            state+=(factor-1)*initial*np.vdot(initial,state)
            # Reversible parity append: the added bit equals k minus the weight
            # on the marked subspace; no postselection or renormalization.
            final=np.zeros(2**n,dtype=complex)
            for index,amplitude in enumerate(state):
                final[2*index+((k-int(weights[index]))%2)]=amplitude
            target=np.array([int(i.bit_count()==k) for i in range(2**n)])/math.sqrt(math.comb(n,k))
            overlap=np.vdot(target,final)
            error=float(np.linalg.norm(final-target*overlap/abs(overlap)))
            assert error<1e-12
            rows.append(dict(N=n,k=k,marked_probability=probability,phase=phase,state_l2_error=error))
    report=dict(status='algebra verified; native oracle and routing not implemented; no score assigned',derivation='On N-1 uniform qubits mark weights k-1,k, with p=C(N,k)/2^(N-1). For p>=1/4 choose phi=acos(1-1/(2p)). Apply the marked-subspace phase exp(i phi), then I+(exp(i phi)-1)|s><s|. Every unmarked amplitude vanishes. Append k XOR parity into a fresh qubit to obtain D(N,k).',sources=['https://arxiv.org/abs/quant-ph/0006031','https://arxiv.org/abs/quant-ph/0005055'],required_work=['Native nearest-neighbor phase oracle for the two adjacent weights','Native phase on the all-zero state for the reflection','Count all ancillas and emitted moments','Validate all feed-forward branches and whole-diagonal readout if measurements are used'],cases=len(rows),rows=rows)
    Path('research/bonus_band_20261025/band_amplification_proof.json').write_text(json.dumps(report,indent=2))
    print('Algebra verified for',len(rows),'cases; largest state error',max(x['state_l2_error'] for x in rows))


if __name__=='__main__':main()
