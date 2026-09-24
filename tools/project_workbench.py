#!/usr/bin/env python3
"""Project-bound asset browser, shared credential settings and generation review."""
import argparse, json, mimetypes, secrets, threading, time, uuid, webbrowser
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote, quote
from socketserver import ThreadingMixIn
import settings_server, asset_workflow
from adapters.assets import credential_store, generation_approval
from workbench import asset_browser as browser, art_registry as registry

WEB=Path(__file__).with_name('workbench')/'web'


class WorkbenchServer(ThreadingMixIn, settings_server.SettingsServer):
    daemon_threads=True
    def __init__(self, project, port=0, job_id=None, view='assets'):
        project=Path(project).resolve()
        if not project.is_dir():raise ValueError('游戏项目目录不存在')
        super().__init__(port,project,job_id,handler=Handler)
        self.cookie_name='oagd_workbench_'+str(self.server_port)
        self.view='tasks' if job_id else view
        self.art_lock=threading.Lock()
        self.session_lock=threading.Lock()
    @property
    def launch_url(self):
        query='?job='+quote(self.job_id) if self.job_id else ''
        return self.origin+'/'+query+'#'+self.view
    def snapshot(self):
        result=browser.scan(self.project)
        result.update(projectKey='current',assetBase='/asset/current/')
        for asset in result['assets']:
            asset['url']=result['assetBase']+quote(asset['path'],safe='/')
            asset['assetRoot']=result['assetBase']
            if asset.get('previewPath'):asset['previewUrl']=result['assetBase']+quote(asset['previewPath'],safe='/')
        result['artAudit']['document']=registry.document_path(self.project).relative_to(self.project).as_posix()
        return result


def job_summary(root,job):
    parameters=job['request']['parameters']
    prompt=parameters.get('prompt',parameters.get('Prompt',''))
    return {'id':job['job_id'],'title':str(prompt).splitlines()[0][:50] if prompt else job['job_id'],
            'provider':job['provider'],'status':job['status'],'createdAt':job['created_at'],
            'parameters':parameters,'inputs':[{k:x[k] for k in ('path','sha256')} for x in job['request']['inputs']],
            'artifacts':[{'path':x['path'],'sha256':x['sha256']} for x in job['artifacts']],
            'attempts':len(job['attempts']),'remoteId':job.get('provider_job_id'),
            'api':job['settings'].get('mode')=='api'}


class Handler(settings_server.Handler):
    def authorized(self,write=False):
        if not self._host() or self.headers.get('Sec-Fetch-Site')=='cross-site':
            self._reply(403,{'error':'请使用当前项目的本机启动地址。'});return False
        if not self._session():
            self._reply(401,{'error':'浏览器连接已失效，请刷新页面重新连接。'});return False
        if write and (self.headers.get('Origin')!=self.server.origin or not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),self.server.csrf)):
            self._reply(403,{'error':'项目会话校验失败，请重新打开看板。'});return False
        self.server.last_access=time.monotonic();return True
    def body(self):
        size=int(self.headers.get('Content-Length','0'))
        if self.headers.get('Content-Type')!='application/json' or self.headers.get('Transfer-Encoding') or not 0<size<=65536:raise ValueError('请求格式或大小无效')
        data=json.loads(self.rfile.read(size))
        if not isinstance(data,dict):raise ValueError('需要 JSON 对象')
        return data
    def do_GET(self):
        parsed=urlsplit(self.path);route=unquote(parsed.path);query=parse_qs(parsed.query)
        if not self._host():return self._reply(403,{'error':'启动地址无效'})
        if route.startswith(('/api/','/asset/')) and not self.authorized():return
        if route.startswith('/api/') and query.get('project',['current'])[0]!='current':return self._reply(404,{'error':'项目不存在'})
        root=self.server.project
        try:
            if route=='/api/session':return self._reply(200,{'csrf':self.server.csrf,'project':str(root),'connectionMode':'local-browser'})
            if route=='/api/state':return self._reply(200,self.server.state())
            if route=='/api/projects':return self._reply(200,{'projects':[{'key':'current','name':browser.game_name({'root':root,'name':root.name}),'root':str(root)}]})
            if route=='/api/assets':return self._reply(200,self.server.snapshot())
            if route=='/api/art-audit':return self._reply(200,self.server.snapshot()['artAudit'])
            if route=='/api/art-source':
                if query.get('source',['direction'])[0]!='direction':raise ValueError('来源不存在')
                path=registry.document_path(root)
                return self._reply(200,{'path':path.relative_to(root).as_posix(),'text':path.read_text(encoding='utf-8-sig'),'title':'Art Direction'})
            if route=='/api/jobs':
                jobs=[];invalid=0
                for path in root.glob('.openaigame/asset-jobs/*/job.json'):
                    try:jobs.append(job_summary(root,asset_workflow.read_job(root,path.parent.name)[1]))
                    except (OSError,ValueError,KeyError,TypeError):invalid+=1
                return self._reply(200,{'jobs':sorted(jobs,key=lambda j:j['createdAt'],reverse=True),'unreadable':invalid})
            if route=='/api/job-review':
                job_id=query.get('job',[''])[0]
                job=asset_workflow.read_job(root,job_id)[1]
                approval=self.server.state(job_id)['approval'] if job['status']=='queued' and job['settings'].get('mode')=='api' else None
                return self._reply(200,{'job':job_summary(root,job),'approval':approval})
            if route.startswith('/api/'):return self._reply(404,{'error':'接口不存在'})
            if route.startswith('/asset/current/'):
                relative=route[len('/asset/current/'):];path=registry.asset_path(root,relative)
                if path.suffix.lower() not in {*browser.KINDS,'.bin','.mtl'} and not path.name.endswith('.vfx.json'):raise ValueError('不支持的文件')
                if relative.startswith('.openaigame/'):
                    known=browser.library_metadata(root)
                    if relative not in known:
                        # Permit only glTF dependencies explicitly referenced by a registered model.
                        allowed=False
                        for model in known:
                            if model.endswith('.gltf'):
                                source=registry.asset_path(root,model)
                                if source.stat().st_size>4*1024*1024:continue
                                data=json.loads(source.read_text(encoding='utf-8-sig'))
                                for entry in data.get('buffers',[])+data.get('images',[]):
                                    uri=entry.get('uri','')
                                    if uri and not urlsplit(uri).scheme and (source.parent/unquote(uri)).resolve()==path:allowed=True
                        if not allowed:raise ValueError('文件未登记')
                return self.file(path,asset=True)
            return self.file(browser.within(WEB,'index.html' if route=='/' else route.lstrip('/')))
        except (OSError,ValueError,KeyError,TypeError):return self._reply(404,{'error':'记录或文件无法读取，请检查项目文件后刷新。'})
    def do_POST(self):
        route=urlsplit(self.path).path
        if route=='/session':
            # Local browser access is intentional. Cross-origin websites must not
            # bootstrap a session: require exact Host/Origin and a non-simple POST.
            if (not self._host() or self.headers.get('Origin')!=self.server.origin
                or self.headers.get('Sec-Fetch-Site') not in (None,'same-origin')
                or self.headers.get('X-Workbench-Connect')!='1'):
                return self._reply(403,{'error':'请直接在本机浏览器中打开看板地址。'})
            try:
                if self.body():raise ValueError('Unexpected connection parameters')
            except (ValueError,TypeError):return self._reply(400,{'error':'连接请求格式无效，请刷新页面。'})
            with self.server.session_lock:
                self.server.last_access=time.monotonic()
                return self._reply(200,{'connected':True,'connectionMode':'local-browser','project':str(self.server.project)},
                    cookie=self.server.cookie_name+'='+self.server.session+'; HttpOnly; SameSite=Strict; Path=/')
        if not self.authorized(write=True):return
        if route in ('/api/save','/api/remove','/api/close'):return super().do_POST()
        root=self.server.project
        try:
            data=self.body()
            if data.get('project','current')!='current':raise ValueError('项目不存在')
            if route=='/api/jobs':
                provider=data.get('provider');prompt=data.get('prompt')
                if provider not in ('tripo','hunyuan3d') or not isinstance(prompt,str) or not 1<=len(prompt.strip())<=1200:raise ValueError('请填写服务与制作需求')
                config_path=root/'.openaigame/asset-providers.json'
                if not config_path.resolve().is_relative_to(root):raise ValueError('配置路径无效')
                config=json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.exists() else {}
                settings=config[provider] if provider in config else credential_store.default_settings(provider)
                if not isinstance(settings,dict) or settings.get('mode')!='api':raise ValueError('先配置生成服务；本页面新建任务仅支持 API 模式')
                parameters={'prompt':prompt.strip(),'type':'text_to_model'} if provider=='tripo' else {'Prompt':prompt.strip()}
                job=asset_workflow.new_job(root,provider,{'parameters':parameters,'inputs':[]},settings)
                return self._reply(201,{'job':job_summary(root,job)})
            if route=='/api/job-approve':
                if set(data)!={'job','fingerprint','accept_charge'} or data['accept_charge'] is not True:raise ValueError('请明确确认本次请求及可能费用')
                current=self.server.state(data['job']).get('approval') or {}
                if current.get('error'):return self._reply(409,{'error':current['error']})
                if not current.get('fingerprint') or current['fingerprint']!=data['fingerprint']:return self._reply(409,{'error':'任务或账户已变化，请刷新后核对'})
                generation_approval.approve(current['fingerprint'])
                return self._reply(200,{'approved':True,'message':'本次请求已授权，等待助手执行。'})
            if route.startswith('/api/art-'):
                with self.server.art_lock:
                    if route=='/api/art-initialize':registry.initialize(root)
                    else:self.edit_art(route,data)
                return self._reply(200,self.server.snapshot())
            return self._reply(404,{'error':'接口不存在'})
        except registry.RevisionConflict as error:return self._reply(409,{'error':str(error)})
        except (ValueError,TypeError,KeyError):return self._reply(400,{'error':'记录未保存。请检查输入、文档格式、服务配置与任务状态。'})
        except OSError:return self._reply(409,{'error':'无法读写项目或本机授权记录，请检查当前用户权限。'})
    def edit_art(self,route,data):
        root=self.server.project;art=registry.load(root);revision=data.get('revision')
        if art['revision']!=revision:raise registry.RevisionConflict('Art Direction 已被修改，请刷新后再保存')
        assets=browser.scan(root)['assets'];lookup={a['path']:a for a in assets}
        if route=='/api/art-register':
            paths=data.get('paths')
            if not isinstance(paths,list) or not 1<=len(paths)<=500 or any(not isinstance(p,str) for p in paths):raise ValueError('请选择资产')
            registry.register(root,art,assets,paths)
        elif route in ('/api/art-record','/api/art-object'):
            object_id=data.get('objectId');definition=data.get('object')
            if definition is not None:
                if not isinstance(definition,dict):raise ValueError('对象无效')
                label=definition.get('label');tags=registry.validate_tags(definition.get('tags'));object_id=definition.get('id')
                if not isinstance(label,str) or not 1<=len(label.strip())<=64 or label.strip()=='—' or any(ord(c)<32 for c in label) or not tags:raise ValueError('对象无效')
                if object_id is not None and (not isinstance(object_id,str) or object_id not in art['objects']):raise ValueError('对象不存在')
                object_id=object_id or 'O'+uuid.uuid4().hex[:16]
                art['objects'][object_id]={'id':object_id,'label':label.strip(),'tags':tags}
            if not isinstance(object_id,str) or object_id not in art['objects']:raise ValueError('对象不存在')
            if route=='/api/art-record':
                path=data.get('path')
                if not isinstance(path,str) or path not in lookup:raise ValueError('资产不存在')
                registry.register(root,art,assets,[path]);art['assets'][path]['objectId']=object_id
            elif definition is None:raise ValueError('对象信息缺失')
        else:raise ValueError('接口不存在')
        registry.write(root,art,revision)
    def file(self,path,asset=False):
        if not path.is_file():return self._reply(404,{'error':'文件不存在'})
        size=path.stat().st_size;start=0;end=size-1;status=200
        value=self.headers.get('Range','')
        if value:
            if not value.startswith('bytes=') or ',' in value:return self._reply(416,{'error':'无效范围'})
            a,b=value[6:].split('-',1)
            if a:start=int(a);end=min(int(b) if b else end,end)
            elif b:start=max(0,size-int(b))
            if start<0 or start>end or start>=size:return self._reply(416,{'error':'范围超出文件'})
            status=206
        self.send_response(status)
        self.send_header('Content-Type',browser.MIME.get(path.suffix.lower(),mimetypes.guess_type(path.name)[0] or 'application/octet-stream'))
        self.send_header('Content-Length',str(max(0,end-start+1)));self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('Content-Security-Policy',"sandbox; default-src 'none'; frame-ancestors 'none'" if asset else "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' blob:; worker-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with path.open('rb') as stream:
                stream.seek(start);remain=end-start+1
                while remain>0:
                    chunk=stream.read(min(65536,remain))
                    if not chunk:break
                    self.wfile.write(chunk);remain-=len(chunk)
        except (BrokenPipeError,ConnectionResetError):pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--view',choices=('assets','tasks','services'),default='assets')
    parser.add_argument('--approve-job')
    parser.add_argument('--no-open',action='store_true')
    parser.add_argument('--ready-file',type=Path)
    parser.add_argument('--idle-minutes',type=int,default=120)
    args=parser.parse_args()
    if not 0<=args.port<=65535 or not 1<=args.idle_minutes<=1440:parser.error('端口或超时无效')
    try:
        if args.approve_job:asset_workflow.read_job(args.project.resolve(),args.approve_job)
        with WorkbenchServer(args.project,args.port,args.approve_job,args.view) as server:
            if args.ready_file:
                args.ready_file.parent.mkdir(parents=True,exist_ok=True)
                with args.ready_file.open('x',encoding='utf-8') as stream:json.dump({'url':server.launch_url,'project':str(server.project)},stream)
            print('项目看板：'+server.launch_url,flush=True)
            def expire():
                while time.monotonic()-server.last_access<args.idle_minutes*60:time.sleep(10)
                server.shutdown()
            threading.Thread(target=expire,daemon=True).start()
            if not args.no_open:webbrowser.open(server.launch_url)
            try:server.serve_forever(poll_interval=.2)
            except KeyboardInterrupt:pass
            finally:
                if args.ready_file:args.ready_file.unlink(missing_ok=True)
        return 0
    except (OSError,ValueError):print('无法启动项目看板，请检查项目路径、端口和启动文件。');return 2


if __name__=='__main__':raise SystemExit(main())
