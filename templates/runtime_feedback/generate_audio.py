"""Original deterministic calibration cues for the engineering example, not final game audio."""
from pathlib import Path
import hashlib,json,math,random,struct,wave

def generate(directory):
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    rate=44100;files=[]
    for name,duration in [('door',.55),('ui',.28),('action',.65),('zone',1.0)]:
        noise=random.Random(812);samples=[]
        for i in range(round(rate*duration)):
            t=i/rate
            envelope=min(1,t/.012)*min(1,(duration-t)/.035)
            if name=='door':value=(.5*math.sin(2*math.pi*(140*t-60*t*t))+.18*noise.uniform(-1,1))*math.exp(-6*t)
            elif name=='ui':value=.45*(math.sin(2*math.pi*740*t)+.4*math.sin(2*math.pi*1110*t))*math.exp(-9*t)
            elif name=='action':value=(.35*math.sin(2*math.pi*(260*t-140*t*t))+.2*noise.uniform(-1,1))*math.exp(-5*t)
            else:
                # Integer-period harmonics and periodic envelope: continuous loop seam.
                value=.3*(math.sin(2*math.pi*220*t)+.3*math.sin(2*math.pi*440*t))*(.8+.2*math.cos(2*math.pi*t))
                envelope=1
            samples.append(round(max(-1,min(1,value*envelope))*.6*32767))
        target=root/(name+'.wav')
        with wave.open(str(target),'wb') as out:
            out.setparams((1,2,rate,len(samples),'NONE','not compressed'))
            out.writeframes(struct.pack('<'+'h'*len(samples),*samples))
        files.append({'id':name,'file':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'sample_rate':rate,'channels':1,'duration_seconds':duration,'source':'generate_audio.py: original additive/noise calibration recipe; no third-party samples','use':'loop' if name=='zone' else 'one-shot'})
    (root/'source-manifest.json').write_text(json.dumps({'schema':1,'purpose':'Engineering feedback cues; listening acceptance separate','assets':files},indent=2),encoding='utf-8')
    return files

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);generate(p.parse_args().directory)
