// Standalone gameplay harness. Dormant unless -oagdPlayback <request.json> is present.
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace OAGD {
[Serializable] public class PlaybackAction { public float at; public string op,target,method,argument; public float[] position; }
[Serializable] public class PlaybackRequest {
    public string request_id,session,scene,camera;
    public float seconds,capture_interval,max_p95_ms;
    public PlaybackAction[] actions;
}
[Serializable] public class PlaybackResult {
    public string request_id,scope="standalone game frame time; development build",error;
    public bool success;
    public int frames,actions_completed,captures;
    public float mean_ms,p95_ms,max_ms;
}
public class OAGDPlayback : MonoBehaviour {
    PlaybackRequest request; PlaybackResult result;
    List<float> times=new List<float>(); float started,nextCapture; int step; bool finished;
    string framesPath;
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Boot() {
        string[] args=Environment.GetCommandLineArgs(); int index=Array.IndexOf(args,"-oagdPlayback");
        if(index<0 || index+1>=args.Length) return;
        var obj=new GameObject("OAGD_PlaybackHarness"); DontDestroyOnLoad(obj);
        var harness=obj.AddComponent<OAGDPlayback>();
        harness.request=JsonUtility.FromJson<PlaybackRequest>(File.ReadAllText(args[index+1]));
        harness.result=new PlaybackResult{request_id=harness.request.request_id};
        harness.framesPath=Path.Combine(harness.request.session,"frames"); Directory.CreateDirectory(harness.framesPath);
        harness.started=Time.realtimeSinceStartup; harness.nextCapture=0;
        Application.logMessageReceived+=harness.OnLog;
    }
    void OnLog(string text,string stack,LogType type) {
        if(type==LogType.Error || type==LogType.Exception || type==LogType.Assert) result.error=(result.error??"")+text+"\n";
    }
    GameObject Find(string path) {
        var matches=SceneManager.GetActiveScene().GetRootGameObjects().SelectMany(g=>g.GetComponentsInChildren<Transform>(true))
            .Where(t=>ObjectPath(t)==path).ToArray();
        if(matches.Length!=1) throw new Exception("Runtime target must be unique: "+path);
        return matches[0].gameObject;
    }
    static string ObjectPath(Transform t) { return t.parent==null?t.name:ObjectPath(t.parent)+"/"+t.name; }
    void Capture() {
        var camera=String.IsNullOrEmpty(request.camera)?Camera.main:Find(request.camera).GetComponent<Camera>();
        if(camera==null) throw new Exception("Recording requires an explicit Camera or MainCamera");
        var texture=new RenderTexture(640,360,24); var previous=camera.targetTexture; var active=RenderTexture.active;
        Texture2D image=null;
        try {
            camera.targetTexture=texture; camera.Render(); RenderTexture.active=texture;
            image=new Texture2D(640,360,TextureFormat.RGB24,false); image.ReadPixels(new Rect(0,0,640,360),0,0); image.Apply();
            File.WriteAllBytes(Path.Combine(framesPath,"frame-"+result.captures.ToString("D6")+".png"),image.EncodeToPNG());
            result.captures++;
        } finally { camera.targetTexture=previous; RenderTexture.active=active; texture.Release(); Destroy(texture); if(image!=null) Destroy(image); }
    }
    void Update() {
        if(request==null || finished) return;
        try {
            float elapsed=Time.realtimeSinceStartup-started;
            if(Time.frameCount>2) times.Add(Time.unscaledDeltaTime*1000f);
            var actions=request.actions??new PlaybackAction[0];
            while(step<actions.Length && actions[step].at<=elapsed) {
                var a=actions[step]; var obj=Find(a.target);
                if(a.op=="position") {
                    if(a.position==null || a.position.Length!=3) throw new Exception("position needs xyz");
                    obj.transform.position=new Vector3(a.position[0],a.position[1],a.position[2]);
                } else if(a.op=="message") {
                    // Explicit project-owned gameplay entry point, not a claim of OS/input-system coverage.
                    if(String.IsNullOrEmpty(a.method)) throw new Exception("Message requires method");
                    if(a.argument==null) obj.SendMessage(a.method,SendMessageOptions.RequireReceiver);
                    else obj.SendMessage(a.method,a.argument,SendMessageOptions.RequireReceiver);
                } else throw new Exception("Unsupported playback action: "+a.op);
                File.AppendAllText(Path.Combine(request.session,"actions.jsonl"),JsonUtility.ToJson(a)+"\n");
                step++; result.actions_completed=step;
            }
            if(request.capture_interval>0 && elapsed>=nextCapture) { Capture(); nextCapture=elapsed+request.capture_interval; }
            if(elapsed>=request.seconds) Finish();
        } catch(Exception error) { result.error=error.ToString(); Finish(); }
    }
    void Finish() {
        finished=true; result.frames=times.Count;
        if(times.Count>0) {
            var sorted=times.OrderBy(x=>x).ToArray(); result.mean_ms=times.Average(); result.max_ms=sorted[sorted.Length-1];
            result.p95_ms=sorted[(int)Math.Ceiling(sorted.Length*.95)-1];
        }
        result.success=String.IsNullOrEmpty(result.error) && times.Count>0 && step==(request.actions??new PlaybackAction[0]).Length
            && (request.max_p95_ms<=0 || result.p95_ms<=request.max_p95_ms);
        File.WriteAllLines(Path.Combine(request.session,"frame-times-ms.csv"),new[]{"frame,delta_ms"}.Concat(times.Select((x,i)=>i+","+x.ToString(System.Globalization.CultureInfo.InvariantCulture))));
        File.WriteAllText(Path.Combine(request.session,"playback.json"),JsonUtility.ToJson(result,true));
        Application.logMessageReceived-=OnLog; Application.Quit(result.success?0:1);
    }
}
}
