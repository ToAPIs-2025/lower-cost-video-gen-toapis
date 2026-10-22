import json
from pathlib import Path
import httpx,pytest
from video_gen import VideoClient
from video_gen.config import Config
from video_gen.exceptions import APIError
from video_gen.models import VideoRequest
from video_gen.providers.toapis import ToApisProvider
from video_gen.providers.registry import get_provider_class

def catalog(model):
    preset=json.loads((Path(__file__).parents[1]/'src/video_gen/providers/toapis_presets.json').read_text())[model]
    token=model=='seedance-2-5'
    return {'currency':'USD','data':[{'id':model,'type':'video','prices':[{'conditions':preset['pricing_conditions'],'unit':'1m_tokens' if token else 'second','price_basis':'total_tokens' if token else 'output_seconds','charge_type':'per_token' if token else 'per_second','unit_price':'10' if token else '0.06','group':'test'}]}]}

@pytest.mark.asyncio
@pytest.mark.parametrize('model,duration,resolution',[('seedance-2-5',4,'480p'),('kling-v3',5,'720p')])
async def test_native_sdk_quote_submit_resume_and_result(tmp_path,model,duration,resolution):
    posts=[]
    def handle(req):
        if req.url.path=='/v1/pricing':return httpx.Response(200,json=catalog(model))
        if req.method=='POST':
            body=json.loads(req.content);posts.append(body);assert body['model']==model and body['prompt']=='bottle'
            return httpx.Response(200,json={'id':'unit-task','status':'queued'})
        return httpx.Response(200,json={'id':'unit-task','status':'completed','result':{'data':[{'url':'https://media.example/video.mp4'}]},'billing':{'status':'settled','cost_usd':'0.3','credits':'60'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        cfg=Config(toapis_api_key='test-key',toapis_state_dir=str(tmp_path))
        async with VideoClient(cfg,http) as sdk:
            a=await sdk.generate('toapis',prompt='bottle',model=model,duration=duration,resolution=resolution,extra={'run_id':'test'})
            b=await sdk.generate('toapis',prompt='bottle',model=model,duration=duration,resolution=resolution,extra={'run_id':'test'})
            assert a.task_id==b.task_id and len(posts)==1
            status=await a.status();assert status.state=='succeeded' and status.video_url=='https://media.example/video.mp4' and status.raw['billing']['status']=='settled'
    assert get_provider_class('toapis') is ToApisProvider
    assert all('test-key' not in p.read_text() for p in tmp_path.glob('*.json'))

@pytest.mark.asyncio
async def test_uncertain_post_cannot_buy_replacement(tmp_path):
    calls=[]
    def handle(req):
        if req.url.path=='/v1/pricing':return httpx.Response(200,json=catalog('kling-v3'))
        calls.append(req.method);raise httpx.ReadTimeout('lost response')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        p=ToApisProvider(Config(toapis_api_key='test-key',toapis_state_dir=str(tmp_path)),http);r=VideoRequest(prompt='bottle',model='kling-v3')
        with pytest.raises(httpx.ReadTimeout):await p.submit(r)
        with pytest.raises(APIError,match='no confirmed task ID'):await p.submit(r)
        assert calls==['POST']

@pytest.mark.asyncio
@pytest.mark.parametrize('changes',[{'image_url':'https://media.example/ref.png'},{'negative_prompt':'bad'},{'seed':1},{'duration':6},{'resolution':'1080p'},{'aspect_ratio':'1:1'},{'extra':{'audio':True}}])
async def test_unsupported_inputs_fail_before_network(tmp_path,changes):
    def handle(req):raise AssertionError('Network should not be called')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        p=ToApisProvider(Config(toapis_api_key='test-key',toapis_state_dir=str(tmp_path)),http)
        with pytest.raises(APIError):await p.submit(VideoRequest(**{'prompt':'bottle','model':'kling-v3',**changes}))

@pytest.mark.asyncio
@pytest.mark.parametrize('url',['https://evil.example','http://toapis.com','https://toapis.com/v1','https://toapis.com@evil.example'])
async def test_origin_restrictions(url,tmp_path):
    p=ToApisProvider(Config(toapis_api_key='test-key',toapis_base_url=url,toapis_state_dir=str(tmp_path)))
    with pytest.raises(APIError):await p.submit(VideoRequest(prompt='bottle',model='kling-v3'))

@pytest.mark.asyncio
async def test_redirect_is_not_followed(tmp_path):
    seen=[]
    def handle(req):
        seen.append(str(req.url));return httpx.Response(307,headers={'location':'https://evil.example'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle),follow_redirects=True) as http:
        p=ToApisProvider(Config(toapis_api_key='test-key',toapis_state_dir=str(tmp_path)),http)
        with pytest.raises(APIError):await p.submit(VideoRequest(prompt='bottle',model='kling-v3'))
        assert len(seen)==1 and 'evil.example' not in seen[0]

@pytest.mark.asyncio
async def test_live_in_progress_status_normalizes_to_running(tmp_path):
    def handle(req):return httpx.Response(200,json={'id':'existing-task','status':'in_progress','progress':0.2})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        p=ToApisProvider(Config(toapis_api_key='test-key',toapis_state_dir=str(tmp_path)),http)
        result=await p.get_status('existing-task');assert result.state=='running' and result.video_url is None
