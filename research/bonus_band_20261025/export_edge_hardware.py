"""Build a standalone, bounded-domain W-selector candidate for validation.

This writes edge_hardware_submission.py; promotion is a separate evidence-based
step. The input native_submission.py and maintained solver are not changed.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).parent


def body_before_main(path):
    text=path.read_text()
    tree=ast.parse(text)
    lines=text.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node,ast.If) and '__name__' in ast.unparse(node.test):
            return ''.join(lines[:node.lineno-1])
    return text


def main():
    bonus_source=(ROOT/'native_submission.py').read_text()
    marker='# Offline-selected native bonus circuits; all synthesis is complete.'
    assert bonus_source.count(marker)==1
    base=(ROOT/'edge_primary_snapshot.py').read_text()+'\n\n'+marker+bonus_source.split(marker,1)[1]
    sensitivity=body_before_main(ROOT/'w_z_sensitivity.py')
    sensitivity=sensitivity.replace('from .w_state_cost import T1, T2, DUR_CZ, DUR_1Q, rate',
                                    'T1=68e-6\nT2=89e-6\nDUR_CZ=42e-9\nDUR_1Q=25e-9')
    coupling=body_before_main(ROOT/'w_zz_sensitivity.py')
    coupling=coupling.replace('from .w_z_sensitivity import apply_gate\n','')
    coupling=coupling.replace('from .w_state_cost import DUR_CZ,DUR_1Q\n','')
    coupling=coupling.replace('def coefficients(', 'def uniform_coefficients(')
    edge=body_before_main(ROOT/'w_edge_sensitivity.py')
    edge=edge.split('\ndef check():',1)[0]
    edge=edge.replace('from .w_state_cost import DUR_CZ, DUR_1Q\n','')
    edge=edge.replace('from .w_z_sensitivity import apply_gate\n','')
    selector=body_before_main(ROOT/'w_edge_selection.py')
    for line in ['from .w_cost_selection import baseline\n','from .w_state_cost import rate\n','from .w_z_sensitivity import probabilities\n','from .w_zz_sensitivity import coefficients as uniform_coefficients\n','from .w_edge_sensitivity import coefficients, signs\n']:
        selector=selector.replace(line,'')
    selector=selector.replace('def select(', 'def _select_w(').replace('baseline.','_W_BASELINE.')
    api=['create_dicke_state','make_chip','rate','readout_bias','prim_tree','bfs_tree','bias_tree',
         'broadcast_order','compile_circuit','w_ops','idle_penalty','shots']
    text=base+'\n\n# Experimental guarded main-path improvement; bonus tables are preserved.\n'
    text+='import types as _w_types\n_original_create_dicke_state=create_dicke_state\n'
    text+='_W_BASELINE=_w_types.SimpleNamespace('+','.join(f'{name}={name}' for name in api)+')\n'
    text+=sensitivity+'\n'+coupling+'\n'+edge+'\n'+selector
    text+='''

def create_dicke_state(num_qubits, num_excitations, cz_pauli_error_rate,
                       sq_pauli_error_rate, zero_errors, one_errors,
                       dynamical_decoupling=True, pack=False, use_blocks=True):
    n,k=int(num_qubits),int(num_excitations)
    if n in (8,10) and k==1 and dynamical_decoupling and not pack:
        cal=(cz_pauli_error_rate,sq_pauli_error_rate,zero_errors,one_errors)
        _,_,circuit,qubits,_=_select_w(n,cal)
        check_circuit(circuit,cz_pauli_error_rate,sq_pauli_error_rate)
        return circuit,set(qubits)
    return _original_create_dicke_state(num_qubits,num_excitations,cz_pauli_error_rate,
                                       sq_pauli_error_rate,zero_errors,one_errors,
                                       dynamical_decoupling,pack,use_blocks)
'''
    ast.parse(text)
    destination=ROOT/'edge_hardware_submission.py';destination.write_text(text)
    manifest=dict(status='standalone candidate; not promoted to native_submission',candidate=destination.name,
                  candidate_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),domain='N in {8,10}, k=1, default DD enabled and pack=False; all other calls use preserved baseline',
                  sources={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                           ['native_submission.py','edge_primary_snapshot.py','edge_primary_origin.json','w_z_sensitivity.py','w_zz_sensitivity.py','w_edge_sensitivity.py','w_edge_selection.py','export_edge_hardware.py']})
    (ROOT/'edge_export_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(destination,len(text),'bytes',flush=True)


if __name__=='__main__':main()
