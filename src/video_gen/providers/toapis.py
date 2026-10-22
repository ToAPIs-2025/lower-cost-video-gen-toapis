"""Optional ToAPIs video provider, with durable paid-submission protection."""
from __future__ import annotations
from pathlib import Path
from decimal import Decimal
from urllib.parse import urlparse,quote
import hashlib,json,os
from ..exceptions import APIError,ProviderNotConfigured
from ..models import TaskRef,TaskStatus,VideoRequest
from .base import BaseProvider
from .toapis_billing import current_price

class ToApisProvider(BaseProvider):
    name='toapis'

    def is_configured(self)->bool:
        return bool(self.config.toapis_api_key)

    def _origin(self)->str:
        u=urlparse(self.config.toapis_base_url)
        if u.scheme!='https' or u.hostname not in ('toapis.com','toapis.cn') or u.port or u.username or u.password or u.path not in ('','/') or u.query or u.fragment:
            raise APIError('Use an exact HTTPS ToAPIs origin without /v1')
        return self.config.toapis_base_url.rstrip('/')

    def _headers(self)->dict[str,str]:
        if not self.is_configured():raise ProviderNotConfigured('Set TOAPIS_API_KEY privately')
        return {'Authorization':'Bearer '+self.config.toapis_api_key,'Content-Type':'application/json'}

    async def _json(self,path:str,body:dict|None=None)->dict:
        url=self._origin()+'/v1/'+path
        # Explicitly forbid redirects so a credential or paid POST cannot be replayed.
        response=await (self.client.post(url,json=body,headers=self._headers(),follow_redirects=False) if body is not None else self.client.get(url,headers=self._headers(),follow_redirects=False))
        if not 200<=response.status_code<300:raise APIError('ToAPIs request failed; inspect the saved task before retrying',response.status_code)
        data=response.json()
        if not isinstance(data,dict):raise APIError('Expected a JSON object')
        return data

    async def submit(self,request:VideoRequest)->TaskRef:
        model=request.model or 'kling-v3'
        if request.image_url or request.negative_prompt or request.seed is not None:raise APIError('This provider currently maps text-to-video only; image, seed and negative prompt are not mapped')
        if set(request.extra)-{'run_id','max_usd'}:raise APIError('Unsupported extra field')
        if not request.prompt.strip() or request.aspect_ratio!='16:9':raise APIError('A prompt and 16:9 aspect ratio are required')
        if model=='seedance-2-5' and request.duration==4 and request.resolution=='480p':
            body={'model':model,'prompt':request.prompt,'duration':4,'resolution':'480p','aspect_ratio':'16:9','generate_audio':False,'output_format':'mp4'}
            conditions={'duration':4,'resolution':'480p','has_video_input':False,'has_image_input':False,'capability':'text2video','generate_audio':False}
        elif model=='kling-v3' and request.duration==5 and request.resolution=='720p':
            body={'model':model,'prompt':request.prompt,'duration':5,'mode':'std','aspect_ratio':'16:9','audio':False}
            conditions={'duration':5,'mode':'std','audio':False,'capability':'text2video','has_video_input':False}
        else:raise APIError('Reviewed presets: seedance-2-5 4s/480p or kling-v3 5s/std/720p, audio off')
        # Catalog conditions must match the exact request. No hard-coded price fallback.
        presets=json.loads(Path(__file__).with_name('toapis_presets.json').read_text(encoding='utf-8'));preset=presets[model];expected={**preset['request'],'prompt':request.prompt}
        if body!=expected:raise APIError('Request differs from reviewed preset')
        catalog=await self._json('pricing?model='+quote(model,safe='')+'&type=video')
        rate=current_price(lambda _:catalog,model,'video',preset['pricing_conditions'])
        estimate=Decimal(rate['maximum_unit_price'])*(Decimal(request.duration) if rate['unit']=='second' else Decimal(38400)/1000000)
        limit=Decimal(str(request.extra.get('max_usd',self.config.toapis_max_usd)))
        if not limit.is_finite() or limit<=0 or limit>Decimal('0.80') or estimate>limit:raise APIError('Quote exceeds reviewed per-job allowance of at most $0.80')
        run=request.extra.get('run_id') or os.environ.get('TOAPIS_RUN_ID','default')
        if not isinstance(run,str) or not run.strip():raise APIError('Nonempty run_id required')
        identity=hashlib.sha256(json.dumps({'origin':self._origin(),'key_hash':hashlib.sha256(self.config.toapis_api_key.encode()).hexdigest(),'request':body,'run':run},sort_keys=True).encode()).hexdigest()
        state=Path(self.config.toapis_state_dir).resolve();state.mkdir(parents=True,exist_ok=True);path=state/(identity+'.json')
        if path.exists():
            saved=json.loads(path.read_text(encoding='utf-8'))
            if saved.get('task_id'):return TaskRef(task_id=saved['task_id'],provider=self.name,raw={'resumed':True})
            raise APIError('An earlier submission has no confirmed task ID; reconcile it before using a new run_id')
        saved={'status':'submitting','task_id':None,'model':model,'estimate_usd':str(estimate),'pricing':rate}
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(saved,f,indent=2)
        try:
            data=await self._json('videos/generations',body);task=data.get('id')
            if not isinstance(task,str) or not task:raise APIError('No task ID returned; do not repeat creation automatically')
            saved.update(status=data.get('status'),task_id=task,billing=data.get('billing'));path.write_text(json.dumps(saved,indent=2),encoding='utf-8')
            return TaskRef(task_id=task,provider=self.name,raw=data)
        except Exception:
            saved['status']='submission_uncertain';path.write_text(json.dumps(saved,indent=2),encoding='utf-8');raise

    async def get_status(self,task_id:str)->TaskStatus:
        data=await self._json('videos/generations/'+quote(task_id,safe=''));status=data.get('status');mapping={'queued':'pending','pending':'pending','in_progress':'running','processing':'running','running':'running','completed':'succeeded','failed':'failed','cancelled':'cancelled','expired':'failed'}
        if status not in mapping:raise APIError('Unknown ToAPIs task status')
        output=None
        if status=='completed':
            rows=(data.get('result') or {}).get('data') or []
            output=rows[0].get('url') if rows else None;u=urlparse(output or '')
            if u.scheme!='https' or not u.hostname or u.username or u.password:raise APIError('Completed task has no safe HTTPS result URL')
        return TaskStatus(task_id=task_id,provider=self.name,state=mapping[status],video_url=output,error='Task failed; inspect private receipt' if status in ['failed','expired'] else None,raw=data)
