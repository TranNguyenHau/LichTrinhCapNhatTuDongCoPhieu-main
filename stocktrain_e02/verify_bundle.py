"""Static inspection of 25 artifacts + 25 roundtrip rows; no model inference."""
import csv
import json
from .config import BUNDLE_ROOT, SYMBOLS, MODEL_NAMES
from .model_service import manifest_info

def main():
    m, digest = manifest_info()
    assert len(m['artifacts'])==25
    for art in m['artifacts']:
        p = BUNDLE_ROOT / art['path']
        cfg = json.loads((p/'config.json').read_text(encoding='utf-8'))
        assert cfg['experiment_id']==m['experiment_id'] and cfg['target_mode']=='T0_raw_return'
        for f in [cfg['model_file'],'scaler_X.joblib','scaler_y.joblib','features.json','metrics.json']:
            assert (p/f).is_file(),f'Missing {p/f}'
    with (BUNDLE_ROOT/'roundtrip_test.csv').open(encoding='utf-8-sig', newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==25 and all(row['status']=='PASS' for row in rows)
    print(f'OK: {len(m["artifacts"])} artifacts, 25/25 roundtrip PASS, bundle SHA256={digest}')
    print('INFO: trained_until 2025-08-19 (historical model; not yet validated on latest production data)')

if __name__=='__main__':
    main()
