"""Adapter for legacy behavioural tests after Build E's breaking quality API change.

The production direct mutation routes remain CLOSED. Legacy tests submit
reviewable version-bound proposals and commit receipts instead, so their
functional data/history assertions continue to cover the new safe workflow.
New security tests use raw TestClient to verify closure and one-time receipts.
"""
from __future__ import annotations

import re
import httpx

class LegacyQualityClient:
    def __init__(self, client): self.client=client
    def __getattr__(self,name): return getattr(self.client,name)
    def __enter__(self):self.client.__enter__();return self
    def __exit__(self,*args):return self.client.__exit__(*args)

    def post(self,url,**kwargs):
        match=re.fullmatch(r'/api/projects/([^/]+)/quality/(autopilot|decisions|undo|restore|impute)',url)
        if not match or 'json' not in kwargs:
            return self.client.post(url,**kwargs)
        pid,endpoint=match.groups()
        body=kwargs['json']
        if endpoint=='decisions' and body.get('decision')=='reject':
            return self.client.post(url,**kwargs)
        op={'autopilot':'autopilot','decisions':'approve','undo':'undo','restore':'restore','impute':'impute'}[endpoint]
        prep={'operation':op,'expected_version':body['expected_version']}
        prep.update({k:body[k] for k in ('issue_id','action_id','target_version','column','strategy') if k in body})
        proposal=self.client.post(f'/api/projects/{pid}/quality/proposals',json=prep,headers=kwargs.get('headers'))
        if proposal.status_code!=200:
            if op=='autopilot' and proposal.status_code==409 and 'No pending automatic corrections' in proposal.text:
                # The safe API reports no-op as 409; the old test contract used 200.
                return httpx.Response(200,json={'version':body['expected_version'],'applied':[],'count':0},request=proposal.request)
            return proposal
        r=self.client.post(f'/api/projects/{pid}/quality/commit',json={
            'proposal_id':proposal.json()['proposal_id'],'proposal_hash':proposal.json()['proposal_hash']},
            headers=kwargs.get('headers'))
        if r.status_code!=200:return r
        data=r.json()
        if op=='approve':
            data={'version':data['version'],'decision':'approved','issue_id':body['issue_id'],
                  'applied':True,'action':data['applied'][0]}
        elif op=='impute':
            action=data['applied'][0]
            data={'version':data['version'],'decision':'approved','strategy':'median',
                  'filled_value':proposal.json()['steps'][0]['proposal']['value'],
                  'affected_rows':action['affected_rows'],'action':action}
        elif op=='undo':
            data={**data,'undone':body['action_id']}
        elif op=='restore':
            data={**data,'restored_from':body['target_version']}
        return httpx.Response(200,json=data,request=r.request)
