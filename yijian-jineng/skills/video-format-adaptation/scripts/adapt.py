"""Trim and pad-scale existing videos into new platform formats without overwriting sources."""
import argparse,json,math,shutil,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import inside,save,digest
def command(source,target,width,height,fps,start,duration,ffmpeg):
    if any(isinstance(x,bool) or not isinstance(x,int) or x<64 or x>7680 or x%2 for x in (width,height)): raise ValueError('宽高需64到7680内的偶数')
    if not isinstance(fps,int) or not 1<=fps<=60: raise ValueError('fps需1到60')
    if not isinstance(start,(int,float)) or not math.isfinite(start) or start<0 or (duration is not None and (not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0)): raise ValueError('裁剪时间无效')
    args=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-n']
    if start: args+=['-ss',str(start)]
    args+=['-i',str(source)]
    if duration is not None: args+=['-t',str(duration)]
    vf=f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1'
    return args+['-map','0:v:0','-map','0:a?','-vf',vf,'-r',str(fps),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(target)]
def probe(ffprobe,path):
    r=subprocess.run([ffprobe,'-v','error','-show_streams','-show_format','-of','json',str(path)],capture_output=True,text=True,encoding='utf-8',errors='replace',check=True,timeout=30)
    return json.loads(r.stdout)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','input','output'): p.add_argument('--'+k,required=True)
    p.add_argument('--width',type=int,required=True); p.add_argument('--height',type=int,required=True); p.add_argument('--fps',type=int,default=30); p.add_argument('--start',type=float,default=0); p.add_argument('--duration',type=float); p.add_argument('--ffmpeg',default=shutil.which('ffmpeg')); p.add_argument('--ffprobe',default=shutil.which('ffprobe')); p.add_argument('--apply',action='store_true'); a=p.parse_args()
    source=inside(a.root,a.input,True); target=inside(a.root,a.output)
    if target.suffix.lower()!='.mp4' or target.exists() or Path(str(target)+'.json').exists(): raise ValueError('需新的MP4及报告位置')
    args=command(source,target,a.width,a.height,a.fps,a.start,a.duration,a.ffmpeg or 'ffmpeg')
    if not a.apply: print(json.dumps({'mode':'plan','command':args,'note':'补边保留原画面；需复核字幕与画幅'},ensure_ascii=False)); sys.exit()
    if not a.ffmpeg or not a.ffprobe: raise ValueError('需安装或指定FFmpeg及FFprobe')
    before=probe(a.ffprobe,source); video=next((s for s in before['streams'] if s['codec_type']=='video'),None)
    if not video: raise ValueError('输入没有视频轨')
    total=float(before['format']['duration'])
    if a.start>=total or a.duration is not None and a.start+a.duration>total+.1: raise ValueError('裁剪范围超出实际视频')
    target.parent.mkdir(parents=True,exist_ok=True); subprocess.run(args,check=True,timeout=1800)
    after=probe(a.ffprobe,target); video=next(s for s in after['streams'] if s['codec_type']=='video')
    if video['width']!=a.width or video['height']!=a.height: raise ValueError('输出画幅不符')
    if any(s['codec_type']=='audio' for s in before['streams']) and not any(s['codec_type']=='audio' for s in after['streams']): raise ValueError('转码丢失音轨')
    report={'source_sha256':digest(source),'output_sha256':digest(target),'input':a.input,'output':a.output,'metadata':after,'stage':'rendered-pending-content-review'}; save(str(target)+'.json',report); print(json.dumps(report,ensure_ascii=False))
