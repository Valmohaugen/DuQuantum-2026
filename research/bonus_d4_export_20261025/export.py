"""Build isolated D4-only primary-path prototype with verified bonus cache."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).parent


def main():
    baseline=(ROOT/'baseline.py').read_text()
    bonus=(ROOT/'verified_bonus_source.py').read_text()
    marker='# Offline-selected native bonus circuits; all synthesis is complete.'
    assert bonus.count(marker)==1
    text=baseline+'\n\n'+marker+bonus.split(marker,1)[1]
    text+='''

# Separate experimental D4 primary-path selector; no W selector is composed.
# Synthetic coherent-error benefit remains uncertain. This is not a promotion.
_d4_original_create_dicke_state = create_dicke_state


def create_dicke_state(num_qubits, num_excitations, cz_pauli_error_rate,
                       sq_pauli_error_rate, zero_errors, one_errors,
                       dynamical_decoupling=True, pack=False, use_blocks=True):
    if not (int(num_qubits)==4 and int(num_excitations)==2
            and dynamical_decoupling is True and pack is False and use_blocks is True):
        return _d4_original_create_dicke_state(
            num_qubits,num_excitations,cz_pauli_error_rate,sq_pauli_error_rate,
            zero_errors,one_errors,dynamical_decoupling,pack,use_blocks)
    cal=(cz_pauli_error_rate,sq_pauli_error_rate,zero_errors,one_errors)
    reference,rqs=_d4_original_create_dicke_state(4,2,*cal)
    adj,node=make_chip(*cal,4,2)
    skew={q:rate(one_errors[q])-rate(zero_errors[q]) for q in node}
    bias=lambda qs:readout_bias(qs,4,2,skew)
    # Literal native data are embedded above; no runtime files or synthesis.
    template,_=create_dicke_state_adaptive(4,2)
    logical=sorted(template.all_qubits())
    r0=min(q.row for q in logical);c0=min(q.col for q in logical)
    cells=[(q.row-r0,q.col-c0) for q in logical]
    seq=[tuple(logical.index(q) for q in op.qubits)
         for op in template.all_operations() if len(op.qubits)==2]
    lab=best_patch(adj,node,cells,seq,bias)
    if lab is None:return reference,rqs
    candidate=template.transform_qubits(dict(zip(logical,lab)));cqs=set(lab)
    if estimate_error(candidate,cqs,adj,node,bias)<estimate_error(reference,rqs,adj,node,bias):
        check_circuit(candidate,cz_pauli_error_rate,sq_pauli_error_rate)
        return candidate,cqs
    return reference,rqs
'''
    ast.parse(text)
    path=ROOT/'d4_hardware_submission.py';path.write_text(text)
    (ROOT/'export_manifest.json').write_text(json.dumps(dict(status='Standalone reviewable prototype; no maintained promotion',candidate=path.name,candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256((ROOT/'baseline.py').read_bytes()).hexdigest(),verified_bonus_sha256=hashlib.sha256((ROOT/'verified_bonus_source.py').read_bytes()).hexdigest(),domain='N4,k2,DD=True,pack=False,use_blocks=True only; all other primary calls use unchanged19ace9c baseline.',limitation='No W selector composition. Finite synthetic cohorts have coherent-error uncertainty and individual regressions.'),indent=2)+'\n')
    print(path.name,hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)


if __name__=='__main__':main()
