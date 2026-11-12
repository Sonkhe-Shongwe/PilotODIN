import hashlib
import json
import tempfile
import unittest
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from unittest import mock

import verify_vintage as v


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.day=date(2025,6,15)
        self.local='2025-06-14T09:45:00Z'
        self.utc='2025-06-14T08:45:00Z'
        self.neso={'hash':v.FROZEN_CSV_SHA256,'day':self.day.isoformat(),
                   'periods':48,'publish_label':self.local,
                   'publish_utc_derived_not_independently_verified':self.utc,
                   'publish_utc_derived':self.utc,
                   'mw':{i:1000+i for i in range(1,49)}}

    def payload(self, *,stamp=None, missing=None, bad_value=False,dup=False,other_date=False):
        rows=[]
        for i in range(1,49):
            if i==missing:continue
            rows.append({'dataset':'NDF','demand':1000+i+(1 if bad_value and i==1 else 0),
                         'publishTime':stamp or self.utc,
                         'settlementDate':'2025-06-16' if other_date else self.day.isoformat(),
                         'settlementPeriod':i,'boundary':None})
        if dup:rows.append(rows[0].copy())
        return json.dumps({'data':rows}).encode()

    def test_dst_periods(self):
        self.assertEqual(v.expected_periods(date(2025,3,30)),46)
        self.assertEqual(v.expected_periods(date(2025,10,26)),50)
        self.assertEqual(v.expected_periods(self.day),48)

    def test_strict_full_vintage_match(self):
        result=v.compare(self.neso,self.payload())
        self.assertEqual(result['verdict'],'EXACT_TIMESTAMP_AND_ALL_PERIOD_VALUES_MATCHED_IN_JSON')
        self.assertEqual(result['candidate_vintages'][0]['forecast_values_matching_neso'],48)
        self.assertEqual(result['gate_c'].split(':')[0],'UNVERIFIED')

    def test_equal_values_wrong_publish_time_is_not_full_match(self):
        result=v.compare(self.neso,self.payload(stamp='2025-06-14T08:55:00Z'))
        self.assertEqual(result['verdict'],'VALUES_MATCH_BUT_ISSUANCE_TIMESTAMP_UNVERIFIED')

    def test_modified_value_cannot_match(self):
        result=v.compare(self.neso,self.payload(bad_value=True))
        self.assertEqual(result['verdict'],'NO_COMPLETE_EXACT_NESO_VALUE_AND_TIMESTAMP_MATCH')

    def test_missing_and_duplicate_periods_fail_closed(self):
        for kwargs in [{'missing':48},{'dup':True}]:
            with self.subTest(kwargs=kwargs):
                result=v.compare(self.neso,self.payload(**kwargs))
                self.assertEqual(result['verdict'],'NO_COMPLETE_EXACT_NESO_VALUE_AND_TIMESTAMP_MATCH')

    def test_other_day_does_not_match(self):
        result=v.compare(self.neso,self.payload(other_date=True))
        self.assertEqual(result['verdict'],'NO_ELEXON_NDF_DATA_FOR_TARGET_DAY_IN_RESPONSE')

    def test_offsite_redirect_refused(self):
        class Resp:
            status=200
            def geturl(self):return 'https://other.example.org/unknown.json'
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return self.payload()
        with mock.patch('verify_vintage.urllib.request.urlopen',return_value=Resp()):
            with self.assertRaisesRegex(v.EvidenceError,'redirected'):
                v.fetch_window_for_target(self.day)

    def test_bad_payload(self):
        with self.assertRaises(v.EvidenceError):v.compare(self.neso,b'{"error":"no data"}')

    def test_pinned_synthetic_neso_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'neso_synthetic.csv'
            lines=['Date,Settlement_Period,Demand_Forecast,Publish_Datetime']
            for i in range(1,49):
                lines.append(f'2025-06-15,{i},{1000+i},2025-06-14T09:45:00Z')
            contents=('\n'.join(lines)+'\n').encode()
            p.write_bytes(contents)
            with mock.patch.object(v,'FROZEN_CSV_SHA256',hashlib.sha256(contents).hexdigest()):
                result=v.load_neso(p,self.day)
            self.assertEqual(result['periods'],48)
            self.assertEqual(result['mw'][1],1001)
            self.assertEqual(result['mw'][2],1002)
            self.assertEqual(result['publish_utc_derived'],self.utc)

    def test_mutated_csv_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fake.csv'
            p.write_text('Date,Settlement_Period,Demand_Forecast,Publish_Datetime\n2025-06-15,1,19640,2025-06-14T09:45:00Z\n')
            with self.assertRaisesRegex(v.EvidenceError,'SHA-256'):
                v.load_neso(p,self.day)

    def test_live_fetch_retains_one_day_and_metadata(self):
        fake=self.payload()
        class Resp:
            status=200
            def geturl(self):return v.make_publication_window_url(date(2025,6,15))
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return fake
        with mock.patch('verify_vintage.urllib.request.urlopen', return_value=Resp()) as opener:
            returned=v.fetch_window_for_target(self.day)
        self.assertEqual(returned,fake)
        request=opener.call_args.args[0]
        self.assertIn('2025-06-14T00%3A00%3A00Z',request.full_url)
        self.assertIn('2025-06-14T23%3A59%3A59Z',request.full_url)

if __name__=='__main__': unittest.main()
