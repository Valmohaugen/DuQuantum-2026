"""Read-only statistics from frozen pilot and confirmation measurements."""
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT=Path(__file__).parent


def summarize(data):
    output=[]
    rows={(r['seed'],r['model'],r['variant']):r for r in data['rows']}
    selected={r['seed']:r['selected'] for r in data['selections']}
    for model in data['models']:
        for variant in ('raw_candidate','selected_with_fallback'):
            paired=[p for p in data['paired_differences'] if p['model']==model and p['variant']==variant]
            details=[]
            for pair in paired:
                seed=pair['seed'];name='candidate' if variant=='raw_candidate' else selected[seed]
                before=rows[seed,model,'baseline']['E_score'];after=rows[seed,model,name]['E_score']
                details.append(dict(seed=seed,baseline_E_score=before,selected_E_score=after,
                                    delta=pair['mean_delta'],relative_delta=pair['mean_delta']/before,
                                    paired_MC_standard_error=pair['paired_MC_standard_error']))
            if not details:continue
            values=[d['delta'] for d in details];relative=[d['relative_delta'] for d in details];count=len(values)
            btotal=sum(d['baseline_E_score'] for d in details);ctotal=sum(d['selected_E_score'] for d in details)
            output.append(dict(model=model,variant=variant,seeds=count,mean_delta=statistics.mean(values),
                               calibration_seed_standard_error=statistics.stdev(values)/math.sqrt(count) if count>1 else None,
                               mean_relative_delta=statistics.mean(relative),
                               relative_delta_standard_error=statistics.stdev(relative)/math.sqrt(count) if count>1 else None,
                               mean_paired_MC_standard_error=math.sqrt(sum(d['paired_MC_standard_error']**2 for d in details))/count,
                               baseline_total=btotal,candidate_total=ctotal,total_delta=ctotal-btotal,relative_total_delta=(ctotal-btotal)/btotal,
                               positive_seeds=sum(v>0 for v in values),negative_seeds=sum(v<0 for v in values),ties=sum(v==0 for v in values),
                               per_seed=details,regressions=[d for d in details if d['delta']<0]))
    return output


def main():
    pilot=json.loads((ROOT/'pilot_results.json').read_text());confirmation=json.loads((ROOT/'results.json').read_text())
    pooled={key:pilot[key]+confirmation[key] for key in ('rows','paired_differences','selections')}
    pooled['models']=confirmation['models']
    expected={(seed,model,name) for seed in range(47,79) for model in confirmation['models'] for name in ('baseline','candidate')}
    actual={(r['seed'],r['model'],r['variant']) for r in confirmation['rows']}
    missing=sorted(expected-actual);assert not actual-expected
    summary=dict(status='Complete disjoint confirmation' if not missing else 'Truncated disjoint confirmation',
                 coverage=dict(expected_rows=len(expected),completed_rows=len(actual),missing_rows=missing,
                               completed_seeds=sorted(seed for seed in range(47,79) if all((seed,m,v) in actual for m in confirmation['models'] for v in ('baseline','candidate')))),
                 pilot=summarize(pilot),confirmation=summarize(confirmation),pooled=summarize(pooled),
                 selections=dict(candidate=sum(r['selected']=='candidate' for r in confirmation['selections']),baseline=sum(r['selected']=='baseline' for r in confirmation['selections'])),
                 max_build_seconds=max(r['seconds'] for r in confirmation['selections']),
                 maximum_baseline_state_error=max(r['baseline_state_error'] for r in confirmation['selections']),
                 maximum_candidate_state_error=max(r['candidate_state_error'] for r in confirmation['selections']),
                 elapsed_seconds=confirmation['elapsed_seconds'],budget_seconds=90,
                 interpretation='Report confirmation separately from the six-seed pilot. Calibration-seed standard errors measure observed seed variation, while paired MC errors describe finite score sampling. Totals sum only this D4 case across the declared synthetic calibrations; they are not the challenge aggregate score. No selector tuning or main promotion.',
                 limitations=confirmation['limitations'],
                 inputs={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('pilot_results.json','results.json','prepared_plan.json')})
    (ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    for row in summary['confirmation']:
        if row['variant']=='selected_with_fallback':print(row['model'],row['mean_delta'],row['calibration_seed_standard_error'],row['negative_seeds'],row['relative_total_delta'])
    print('coverage',summary['coverage'])


if __name__=='__main__':main()
