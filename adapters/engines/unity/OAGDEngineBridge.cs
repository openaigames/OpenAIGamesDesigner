// Explicitly installed into Assets/Editor/OpenAIGamesDesigner by engine_setup.py.
using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace OAGD {
    [InitializeOnLoad]
    public static class EngineBridge {
        const string Key = "OAGD.EngineSmoke.Request";
        [Serializable] class Request {
            public string report, scene, target, output;
            public string[] scenes;
            public double seconds;
            public bool development;
        }
        [Serializable] class Result {
            public string project, version, action, message;
            public bool success, entered_play;
            public int errors, frames;
        }
        static EngineBridge() {
            EditorApplication.update += Tick;
            Application.logMessageReceived += Log;
            EditorApplication.playModeStateChanged += state => {
                if (state == PlayModeStateChange.EnteredEditMode && SessionState.GetString(Key, "") != "")
                    SessionState.SetBool(Key+".returnedToEdit", true);
            };
        }
        static string Argument(string name) {
            var args = Environment.GetCommandLineArgs();
            for (int i=0; i<args.Length-1; ++i) if (args[i]==name) return args[i+1];
            throw new Exception("Missing argument " + name);
        }
        static Request Read(string path) { return JsonUtility.FromJson<Request>(File.ReadAllText(path)); }
        static void Finish(Request req, string action, bool ok, int errors, string message, bool entered=false, int frames=0) {
            var result = new Result {project=Directory.GetParent(Application.dataPath).FullName,
                version=Application.unityVersion, action=action, success=ok, errors=errors,
                message=message, entered_play=entered, frames=frames};
            File.WriteAllText(req.report, JsonUtility.ToJson(result, true));
            SessionState.EraseString(Key);
            // Synchronous build commands can exit directly; Play Mode must unwind first.
            if (action == "build") EditorApplication.Exit(ok ? 0 : 1);
            else EditorApplication.delayCall += () => EditorApplication.Exit(ok ? 0 : 1);
        }
        public static void Build() {
            var req = Read(Argument("-oagdRequest"));
            try {
                var target = (BuildTarget)Enum.Parse(typeof(BuildTarget), req.target);
                var result = PlayerBuild.Run(req.scenes, req.output, target, req.development);
                Finish(req, "build", result.summary.result==BuildResult.Succeeded,
                    (int)result.summary.totalErrors, result.summary.result.ToString());
            } catch (Exception e) { Finish(req, "build", false, 1, e.ToString()); }
        }
        public static void Smoke() {
            var path = Argument("-oagdRequest"); var req = Read(path);
            try {
                EditorSceneManager.OpenScene(req.scene, OpenSceneMode.Single);
                SessionState.SetString(Key, path);
                SessionState.SetInt(Key+".errors", 0); SessionState.SetInt(Key+".frames", 0);
                SessionState.SetBool(Key+".entered", false);
                SessionState.SetBool(Key+".completed", false);
                SessionState.SetBool(Key+".returnedToEdit", false);
                SessionState.SetInt(Key+".lastFrame", -1);
                SessionState.SetString(Key+".started", DateTime.UtcNow.Ticks.ToString());
                EditorApplication.isPlaying = true;
            } catch (Exception e) { Finish(req, "smoke", false, 1, e.ToString()); }
        }
        static void Log(string message, string stack, LogType type) {
            if (SessionState.GetString(Key, "")=="") return;
            if (type==LogType.Error || type==LogType.Exception || type==LogType.Assert)
                SessionState.SetInt(Key+".errors", SessionState.GetInt(Key+".errors", 0)+1);
        }
        static void Tick() {
            var path = SessionState.GetString(Key, ""); if (path=="") return;
            var req = Read(path);
            bool entered = SessionState.GetBool(Key+".entered", false);
            int frames = SessionState.GetInt(Key+".frames", 0);
            int errors = SessionState.GetInt(Key+".errors", 0);
            var started = new DateTime(long.Parse(SessionState.GetString(Key+".started", "0")), DateTimeKind.Utc);
            if (EditorApplication.isPlaying) {
                if (!entered) {
                    SessionState.SetBool(Key+".entered", true);
                    SessionState.SetString(Key+".playing", DateTime.UtcNow.Ticks.ToString());
                }
                if (Time.frameCount != SessionState.GetInt(Key+".lastFrame", -1)) {
                    SessionState.SetInt(Key+".frames", frames+1);
                    SessionState.SetInt(Key+".lastFrame", Time.frameCount);
                }
                var playing = new DateTime(long.Parse(SessionState.GetString(Key+".playing", "0")), DateTimeKind.Utc);
                if ((DateTime.UtcNow-playing).TotalSeconds >= req.seconds) {
                    SessionState.SetBool(Key+".completed", true);
                    EditorApplication.isPlaying = false;
                }
            } else if (entered && SessionState.GetBool(Key+".returnedToEdit", false)) {
                bool completed = SessionState.GetBool(Key+".completed", false);
                Finish(req, "smoke", completed && errors==0 && frames>0, errors,
                    completed ? "Play Mode completed" : "Play Mode stopped early", true, frames);
            } else if ((DateTime.UtcNow-started).TotalSeconds > 60) {
                Finish(req, "smoke", false, errors+1, "Play Mode entry timed out", entered, frames);
            }
        }
    }
}
