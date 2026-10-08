using System;
using System.Collections.Generic;
using UnityEngine;
namespace GameActionTiming {
 [Serializable] public class SequenceAsset {public string id,kind,binding;public double duration_s;}
 [Serializable] public class SequenceClip {
  public string id,track,asset;public double start_s,source_in_s,source_out_s,rate=1,blend_in_s,blend_out_s,volume=1;
  [NonSerialized] public SequenceAsset source;
  public double End {get{return start_s+(source_out_s-source_in_s)/rate;}}
 }
 [Serializable] public class SequenceEvent {public string id;public double time_s;}
 [Serializable] public class SequenceWindow {public string id;public double start_s,end_s;}
 [Serializable] public class SequenceData {public string schema,id;public double duration_s;public SequenceAsset[] assets;public SequenceClip[] clips;public SequenceEvent[] events;public SequenceWindow[] windows;}
 public class SequenceSignal {public double time;public string kind,id;public SequenceClip clip;internal int order,index;}
 // A runtime scheduler, not a replacement for Animator/Timeline. Subscribe before
 // StartSequence; bind signals to the project's Playables/Animator and audio.
 public sealed class ActionSequencePlayer {
  public SequenceData Data {get;private set;}
  public bool Running {get;private set;}
  public double Time {get;private set;}
  public event Action<SequenceSignal> Signal;
  readonly List<SequenceSignal> signals=new List<SequenceSignal>();readonly HashSet<SequenceClip> active=new HashSet<SequenceClip>();readonly HashSet<string> windows=new HashSet<string>();int cursor;
  static bool Finite(double x,double min=0,double max=120){return !double.IsNaN(x)&&!double.IsInfinity(x)&&x>=min&&x<=max;}
  void Add(double t,string kind,string id,SequenceClip c,int order){signals.Add(new SequenceSignal{time=t,kind=kind,id=id,clip=c,order=order,index=signals.Count});}
  public ActionSequencePlayer(string json){
   Data=JsonUtility.FromJson<SequenceData>(json);if(Data==null||Data.schema!="action-sequence/1"||!Finite(Data.duration_s,.01))throw new ArgumentException("Invalid sequence");
   var ids=new HashSet<string>();var assets=new Dictionary<string,SequenceAsset>();foreach(var a in Data.assets)assets.Add(a.id,a);
   foreach(var c in Data.clips){if(!ids.Add(c.id)||!assets.ContainsKey(c.asset)||!Finite(c.start_s)||!Finite(c.source_in_s)||!Finite(c.source_out_s)||!Finite(c.rate,.1,4)||!Finite(c.volume,0,2)||!Finite(c.blend_in_s)||!Finite(c.blend_out_s))throw new ArgumentException("Invalid clip");c.source=assets[c.asset];if(c.source_out_s<=c.source_in_s||c.source_out_s>c.source.duration_s+.0001||c.End>Data.duration_s+.0001||c.blend_in_s+c.blend_out_s>c.End-c.start_s+.0001)throw new ArgumentException("Clip exceeds sequence");Add(c.start_s,"clip_start",c.id,c,3);if(c.blend_out_s>0)Add(c.End-c.blend_out_s,"clip_exit",c.id,c,4);Add(c.End,"clip_end",c.id,c,0);}
   foreach(var e in Data.events){if(!ids.Add(e.id)||!Finite(e.time_s,0,Data.duration_s))throw new ArgumentException("Invalid event");Add(e.time_s,"event",e.id,null,2);}
   foreach(var w in Data.windows){if(!ids.Add(w.id)||!Finite(w.start_s)||!Finite(w.end_s,0,Data.duration_s)||w.end_s<=w.start_s)throw new ArgumentException("Invalid window");Add(w.start_s,"window_open",w.id,null,1);Add(w.end_s,"window_close",w.id,null,0);}
   signals.Sort((a,b)=>a.time!=b.time?a.time.CompareTo(b.time):a.order!=b.order?a.order.CompareTo(b.order):a.index.CompareTo(b.index));
  }
  public void StartSequence(){Stop();cursor=0;Time=0;Running=true;Advance(0);}
  public void Advance(double elapsed){if(!Running||!Finite(elapsed,Time,double.MaxValue))return;Time=elapsed;while(Running&&cursor<signals.Count&&signals[cursor].time<=elapsed+.0000001){var s=signals[cursor++];if(s.kind=="window_open")windows.Add(s.id);if(s.kind=="window_close")windows.Remove(s.id);if(s.kind=="clip_start")active.Add(s.clip);if(s.kind=="clip_end")active.Remove(s.clip);Signal?.Invoke(s);}if(elapsed>=Data.duration_s)Running=false;}
  public void Stop(){Running=false;foreach(var id in new List<string>(windows))Signal?.Invoke(new SequenceSignal{time=Time,kind="window_cancel",id=id});windows.Clear();foreach(var c in new List<SequenceClip>(active))Signal?.Invoke(new SequenceSignal{time=Time,kind="clip_cancel",id=c.id,clip=c});active.Clear();Running=false;}
 }
}
