#!/usr/bin/env python3
"""P4-67: No-training, fail-closed NESO vs Elexon NDF historical vintage check.

No data is downloaded or written unless --fetch and --save-json are both given.
All evidence levels are descriptive. A matching vintage does not establish Gate C.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FROZEN_CSV_SHA256 = 'a9992f87a766f3cf3307b24cc7c9940e797bdea855427e6e31647984e27bdc0f'
BASE_URL = 'https://data.elexon.co.uk/bmrs/api/v1/datasets/NDF'
MAX_BYTES = 8_000_000
try:
    UK = ZoneInfo('Europe/London')
except ZoneInfoNotFoundError as err:
    raise SystemExit('ERROR: Europe/London timezone rules unavailable. Use a Python environment with IANA tzdata; no guessed offset or timestamp conversion allowed.') from err


class EvidenceError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_periods(day: date) -> int:
    a = datetime.combine(day, time.min, UK).astimezone(timezone.utc)
    b = datetime.combine(day + timedelta(days=1), time.min, UK).astimezone(timezone.utc)
    return int((b - a).total_seconds() // 1800)


def load_neso(csv_path: Path, target: date):
    raw = csv_path.read_bytes()
    raw_hash = digest(raw)
    if raw_hash != FROZEN_CSV_SHA256:
        raise EvidenceError(f'CSV SHA-256 does not match P4-65 pinned input: {raw_hash}')
    rows = []
    with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        table = csv.DictReader(f)
        required = {'Date', 'Settlement_Period', 'Demand_Forecast', 'Publish_Datetime'}
        if not required.issubset(set(table.fieldnames or [])):
            raise EvidenceError('Missing required NESO CSV fields')
        for row in table:
            if row['Date'] == target.isoformat():
                rows.append(row)
    if not rows:
        raise EvidenceError(f'No NESO target day {target}')
    n = expected_periods(target)
    periods = [int(row['Settlement_Period']) for row in rows]
    if len(periods) != n or sorted(periods) != list(range(1,n+1)):
        raise EvidenceError(f'Invalid NESO settlement day: rows={len(periods)} expected={n} unique={len(set(periods))}')
    dates = {x['Publish_Datetime'] for x in rows}
    if len(dates) != 1:
        raise EvidenceError(f'Inconsistent NESO publication label count {len(dates)}')
    raw_label = next(iter(dates))
    # NESO says GMT/BST wall clock even if the literal source representation ends Z.
    # This is *not* treated as a UTC ISO-8601 timestamp.
    if not raw_label.endswith('Z'):
        raise EvidenceError('Unexpected NESO publish label shape; manual verification needed')
    wall = datetime.fromisoformat(raw_label.removesuffix('Z'))
    if wall.tzinfo is not None:
        raise EvidenceError('Unexpected NESO timezone shape')
    if wall.date() != target - timedelta(days=1):
        raise EvidenceError('NESO publication is not on prior local calendar date')
    # For the unambiguous normal days used here, require only one valid UK offset.
    # Zone folds are ambiguous during the autumn clock change and cannot auto-PASS.
    a = wall.replace(tzinfo=UK, fold=0)
    b = wall.replace(tzinfo=UK, fold=1)
    if a.utcoffset() != b.utcoffset():
        raise EvidenceError('Ambiguous UK publication wall time; manual DST reconciliation needed')
    neso_forecasts = {int(row['Settlement_Period']): Decimal(row['Demand_Forecast']) for row in rows}
    return {'hash':raw_hash, 'day':target.isoformat(), 'periods':n, 'publish_label':raw_label,
            'publish_utc_derived':a.astimezone(timezone.utc).isoformat().replace('+00:00','Z'),
            'mw':neso_forecasts}


def parse_elexon_payload(raw: bytes):
    try:
        obj=json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise EvidenceError(f'Elexon response is not valid JSON: {e}') from e
    if not isinstance(obj,dict) or not isinstance(obj.get('data'),list):
        raise EvidenceError('Elexon payload lacks top-level data array')
    return obj['data']


def valid_elexon_groups(records, target: date, expected: int):
    groups = defaultdict(list)
    invalid = 0
    for record in records:
        if not isinstance(record,dict) or record.get('settlementDate') != target.isoformat():
            continue
        if record.get('dataset') not in (None,'NDF'):
            continue
        # Elexon NDF's national boundary is coded 'N' in the real BMRS feed.
        if record.get('boundary') not in (None, '', 'National', 'N'):
            invalid+=1
            continue
        try:
            time_str = record['publishTime']
            stamp = datetime.fromisoformat(time_str.replace('Z','+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('missing Elexon UTC offset')
            stamp = stamp.astimezone(timezone.utc)
            period = int(record['settlementPeriod'])
            mw=Decimal(str(record['demand']))
            if not mw.is_finite() or period<1 or period>expected:
                raise ValueError('invalid period/demand')
        except (KeyError,TypeError,ValueError,InvalidOperation) as e:
            invalid+=1
            continue
        groups[stamp].append((period, mw))
    return groups,invalid


def compare(neso, elexon_raw: bytes) -> dict:
    records=parse_elexon_payload(elexon_raw)
    day=date.fromisoformat(neso['day'])
    expected=neso['periods']
    groups,invalid=valid_elexon_groups(records,day,expected)
    expected_time=datetime.fromisoformat(neso['publish_utc_derived'].replace('Z','+00:00'))
    result={'target_date':neso['day'], 'neso_file_sha256':neso['hash'],
            'elexon_payload_sha256':digest(elexon_raw), 'elexon_records_total':len(records),
            'elexon_target_vintages':len(groups), 'elexon_target_invalid_rows':invalid,
            'elexon_target_accepted_rows':sum(len(x) for x in groups.values()),
            'neso_publish_label_local_gmt_bst':neso['publish_label'],
            'neso_publish_utc_derived_not_independently_verified':neso['publish_utc_derived'],
            'expected_settlement_periods':expected,'candidate_vintages':[]}
    exact=[]
    value_only=[]
    for stamp, entries in sorted(groups.items()):
        period_ct=Counter(p for p,_ in entries)
        valid_geometry=(len(entries)==expected and set(period_ct)==set(range(1,expected+1))
                        and all(x==1 for x in period_ct.values()))
        elexon_mw={p:mw for p,mw in entries}
        matches=sum(1 for p,mw in neso['mw'].items() if p in elexon_mw and elexon_mw[p]==mw)
        exact_stamp=stamp==expected_time
        candidate={'elexon_publish_utc':stamp.isoformat().replace('+00:00','Z'),
                   'records':len(entries), 'valid_geometry':valid_geometry,
                   'forecast_values_matching_neso':matches, 'of_expected':expected,
                   'exact_derived_publish_time_match':exact_stamp}
        result['candidate_vintages'].append(candidate)
        if valid_geometry and matches==expected:
            value_only.append(candidate)
            if exact_stamp and invalid==0:
                exact.append(candidate)
    if len(exact)==1:
        result['verdict']='EXACT_TIMESTAMP_AND_ALL_PERIOD_VALUES_MATCHED_IN_JSON'
        # Narrow PASS. Even this does NOT establish real business utility or vintage completeness.
    elif len(exact)>1:
        result['verdict']='AMBIGUOUS_MULTIPLE_EXACT_VINTAGES'
    elif value_only:
        result['verdict']='VALUES_MATCH_BUT_ISSUANCE_TIMESTAMP_UNVERIFIED'
    elif not groups:
        result['verdict']='NO_ELEXON_NDF_DATA_FOR_TARGET_DAY_IN_RESPONSE'
    else:
        result['verdict']='NO_COMPLETE_EXACT_NESO_VALUE_AND_TIMESTAMP_MATCH'
    result['gate_c']='UNVERIFIED: independent operational owner, permission, decision intervention and measured utility absent'
    return result


def make_publication_window_url(target: date) -> str:
    publish_date=target-timedelta(days=1)
    # One publication-calendar day, UTC; do NOT invent a fixed operational cutoff.
    args={'publishDateTimeFrom':publish_date.isoformat()+'T00:00:00Z',
          'publishDateTimeTo':publish_date.isoformat()+'T23:59:59Z','format':'json'}
    return BASE_URL+'?'+urllib.parse.urlencode(args)


def fetch_window_for_target(target:date)->bytes:
    url=make_publication_window_url(target)
    req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'PilotODIN-P4-67-research/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            if response.status!=200:
                raise EvidenceError(f'Elexon HTTP {response.status}')
            final_url = urllib.parse.urlsplit(response.geturl())
            if final_url.scheme != 'https' or final_url.hostname != 'data.elexon.co.uk':
                raise EvidenceError(f'Elexon response redirected away from official HTTPS host: {response.geturl()}')
            blob=response.read(MAX_BYTES+1)
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as e:
        raise EvidenceError(f'Could not retrieve Elexon data: {e}') from e
    if len(blob)>MAX_BYTES:
        raise EvidenceError(f'Elexon response too large: >{MAX_BYTES} bytes')
    parse_elexon_payload(blob)  # Refuse to save a partial/non-JSON error page as evidence.
    return blob


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--neso',type=Path,required=True,help='Original P4-65 NESO CSV (pinned SHA-256)')
    parser.add_argument('--target-date',type=date.fromisoformat,default=date(2025,6,15))
    sources=parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--elexon-json',type=Path,help='Use independently saved raw Elexon JSON')
    sources.add_argument('--fetch',action='store_true',help='Issue one live Elexon dataset API request')
    parser.add_argument('--save-json',type=Path,help='Required with --fetch; refuses existing path')
    args=parser.parse_args(argv)
    if args.fetch and not args.save_json:
        parser.error('--fetch requires --save-json to preserve raw evidence')
    if args.save_json and not args.fetch:
        parser.error('--save-json is only accepted with --fetch')
    try:
        neso=load_neso(args.neso,args.target_date)
        if args.fetch:
            if args.save_json.exists():
                raise EvidenceError(f'Refusing to overwrite existing raw evidence: {args.save_json}')
            raw=fetch_window_for_target(args.target_date)
            # Exclusive create, and avoid writing input source or application state.
            with args.save_json.open('xb') as stream:
                stream.write(raw)
            source=str(args.save_json)
        else:
            raw=args.elexon_json.read_bytes()
            if len(raw)>MAX_BYTES:
                raise EvidenceError(f'Elexon input too large: {len(raw)} bytes')
            source=str(args.elexon_json)
        result=compare(neso,raw)
        result['raw_elexon_evidence_path']=source
        result['response_provenance']=('DIRECT_OFFICIAL_ELEXON_HTTPS_REQUEST' if args.fetch
                                      else 'USER_SUPPLIED_JSON_NOT_INDEPENDENTLY_AUTHENTICATED')
        result['official_api_request_url']=make_publication_window_url(args.target_date) if args.fetch else None
        result['exact_field_match_from_official_endpoint']=(args.fetch and result['verdict']=='EXACT_TIMESTAMP_AND_ALL_PERIOD_VALUES_MATCHED_IN_JSON')
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0 if result['exact_field_match_from_official_endpoint'] else 2
    except (EvidenceError, OSError, ValueError) as e:
        print(json.dumps({'verdict':'FAIL_CLOSED','error':str(e),'gate_c':'UNVERIFIED'},indent=2),file=sys.stderr)
        return 2

if __name__=='__main__':
    sys.exit(main())
