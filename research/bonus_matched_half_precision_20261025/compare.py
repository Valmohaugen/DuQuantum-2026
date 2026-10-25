"""Identical native pipeline and supported columns; no fit in this stage."""
import json
import time
import cirq_google
from . import helpers as h
from .harvest import certify

def main():
    start=time.monotonic()
    dev=cirq_google.Willow105.metadata
    qr={q:(1e-3,0.) for q in dev.qubit_set}
    pr={tuple(edge):(1e-3,0.) for edge in dev.qubit_pairs}
    adj,node=h.b.make_chip(pr,qr,qr,qr,15,4)
    rows=[]
    for n,peer in [(6,'peer_00'),(7,'peer_01')]:
        old=json.loads((h.ROOT/f'certified_{n}_3.json').read_text())
        new=json.loads((h.ROOT/f'{peer}.json').read_text())
        oc=certify(old,f'certified-{n}',adj,node)
        nc=certify(new,peer,adj,node)
        assert oc['accepted'] and old['k']==new['k']==3
        rows.append(dict(n=n,supported_r=list(range(4)),certified=oc,peer=nc,
                         strict_depth_opportunity=nc['depth']<oc['depth']))
    report=dict(rows=rows,seconds=time.monotonic()-start,
                pipeline='compile_ops -> optimize -> commuting_schedule(restarts=3), identical path')
    (h.ROOT/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
