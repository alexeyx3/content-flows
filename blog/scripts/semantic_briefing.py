"""Compact agent view of a semantic report; preserve every query and term.

The complete machine report remains authoritative. Location/excerpt arrays are
loaded only for selected IDs, not duplicated into every specialist's context.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def compact(report: dict, coverage_sha256: str) -> dict:
    rows = []
    for row in report['rows']:
        item = {key: row[key] for key in ('id','type','text','variants','query_ids')}
        for key in ('all_stopwords','impressions'):
            if key in row:item[key]=row[key]
        item['counts']={f'{mode}_{period}':row[period][mode] for mode in ('exact','morph') for period in ('before','after')}
        rows.append(item)
    return {'version':1,'coverage_sha256':coverage_sha256,'summary':report['summary'],
            'source_url':report.get('source_url'),'window':report.get('window'),
            'definitions':report['definitions'],'rows':rows,
            'location_lookup':'Read exact_locations/morph_locations for selected IDs in coverage.json. No query or term is truncated here.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args()
    raw=args.report.read_bytes();data=compact(json.loads(raw),hashlib.sha256(raw).hexdigest())
    target=args.report.with_name('briefing.json')
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(f'{target}: {len(data["rows"])} complete rows; no repeated location arrays')


if __name__=='__main__':main()
