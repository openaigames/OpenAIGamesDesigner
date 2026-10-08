"""Validated Tripo multiview snapshots in official [front,left,back,right] order."""
from pathlib import Path
from . import api_common, generation_capabilities
VIEWS=generation_capabilities.TRIPO_VIEWS
def kind(request):
    return request.get('parameters',{}).get('type','image_to_model' if request.get('inputs') else 'text_to_model')
def validate(request):
    generation_capabilities.validate_mode('tripo', request)
    p=request.get('parameters',{})
    inputs=request.get('inputs',[])
    mode=kind(request)
    if mode not in ('text_to_model','image_to_model','multiview_to_model','generate_multiview_image'):
        raise ValueError('Unsupported Tripo generation type')
    if mode=='generate_multiview_image':
        if set(p) != {'type'}:
            raise ValueError('Image to Multiview accepts only the source image; model, prompt and geometry parameters are not supported')
        if len(inputs)!=1 or not isinstance(inputs[0],dict) or inputs[0].get('view','front')!='front':
            raise ValueError('Image to Multiview requires exactly one front image')
        return
    if mode=='text_to_model':
        if inputs or not isinstance(p.get('prompt'),str) or not p['prompt'].strip():
            raise ValueError('Tripo text generation requires a prompt and no images')
        return
    if any(k in p for k in ('prompt','negative_prompt','file','files')):
        raise ValueError('Use project image inputs without text prompts or file tokens')
    if mode=='image_to_model':
        if len(inputs)!=1:raise ValueError('Single-image mode needs exactly one input')
        if isinstance(inputs[0],dict) and inputs[0].get('view') not in (None,'front'):
            raise ValueError('Single image must be the front view')
        return
    if not 2<=len(inputs)<=4 or any(not isinstance(x,dict) for x in inputs):
        raise ValueError('Tripo multiview requires 2–4 explicitly labeled image inputs')
    views=[x.get('view') for x in inputs]
    if 'front' not in views or len(set(views))!=len(views) or any(v not in VIEWS for v in views):
        raise ValueError('Use one front and unique left/back/right views')
    paths=[x.get('snapshot',x.get('path')) for x in inputs]
    if any(not isinstance(x,str) or not x for x in paths) or len(set(paths))!=len(paths):
        raise ValueError('Each view must use a different image')
    hashes=[x.get('sha256') for x in inputs if x.get('sha256')]
    if len(set(hashes))!=len(hashes):raise ValueError('Do not reuse identical images as different views')
def read_images(request):
    validate(request)
    result={}
    for item in request.get('inputs',[]):
        data,ext=api_common.image_input({'inputs':[item]},20*1024**2)
        result[item.get('view','front')]=(data,ext)
    return result
def summary(request):
    validate(request)
    mode=kind(request)
    images=[{'view':x.get('view','front'),'path':x.get('path',x.get('snapshot')),'sha256':x.get('sha256')} for x in request.get('inputs',[])]
    return {'mode':{'text_to_model':'text','image_to_model':'image','multiview_to_model':'multiview','generate_multiview_image':'image_to_multiview'}[mode],
            'prompt_sent':mode=='text_to_model','images':images,
            'wire_view_order':list(VIEWS) if mode=='multiview_to_model' else ['front'],
            'omitted_views':[v for v in VIEWS if v not in [x['view'] for x in images]] if mode=='multiview_to_model' else []}

