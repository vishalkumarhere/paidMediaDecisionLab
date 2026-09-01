import argparse
import json
import sys
from pathlib import Path
from .pipeline import build
from .storage import ROOT

def main():
    parser = argparse.ArgumentParser(description='Build and validate the synthetic Luxe Cafe milestone 2 dataset.')
    sub = parser.add_subparsers(dest='command',required=True)
    b = sub.add_parser('build')
    b.add_argument('--config',type=Path,default=ROOT/'config/default.json')
    b.add_argument('--output',type=Path,default=ROOT/'data/local-run')
    b.add_argument('--seed',type=int)
    b.add_argument('--as-of')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    if args.seed is not None:
        config['seed'] = args.seed
    if args.as_of is not None:
        config['as_of'] = args.as_of
    try:
        result = build(config,args.output)
    except (ValueError,FileExistsError) as exc:
        parser.exit(1,f'Build failed: {exc}\n')
    print(json.dumps({'status':result['status'],'dataset_sha256':result['dataset_sha256'],
        'raw_rows':{k:v['rows'] for k,v in result['raw'].items()},
        'passed_checks':len(result['checks']),'warnings':result['warnings'],
        'output':str(args.output.resolve())},indent=2))

if __name__ == '__main__':
    main()

