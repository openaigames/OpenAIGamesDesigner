using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using UnityEngine;

namespace GameActionTiming {
    [Serializable] public class RecordedEvent {
        public string track, id;
        public double t_s, uncertainty_s;
    }
    [Serializable] public class ActionCapture {
        public string schema = "action-events/1", engine = "unity", clock = "monotonic_seconds";
        public string engine_version, action, revision, source, input_mode, input_description;
        public double zero_s = 0, duration_s;
        public bool complete;
        public int dropped_events;
        public List<RecordedEvent> events = new List<RecordedEvent>();
    }
    // Attach to the same object that receives Animation Events. Call only on the main thread.
    public sealed class ActionEventRecorder : MonoBehaviour {
        private static readonly Regex Token = new Regex(@"^[A-Za-z0-9_.:/-]{1,120}$");
        private readonly Dictionary<string,int> counts = new Dictionary<string,int>();
        private ActionCapture capture;
        private double startTime;
        public bool IsRecording { get; private set; }
        public string LastSavedPath { get; private set; }
        private static void Text(string value) {
            if (string.IsNullOrWhiteSpace(value) || value.Length > 300 || Regex.IsMatch(value, @"[\x00-\x1f]")) throw new ArgumentException("Invalid recording metadata");
        }
        public void StartRecording(string action, string revision, string source, string inputMode, string inputDescription) {
            if (IsRecording) throw new InvalidOperationException("Finish the current recording first");
            foreach (var value in new [] {action, revision, source, inputDescription}) Text(value);
            if (inputMode != "human" && inputMode != "software" && inputMode != "mixed" && inputMode != "unknown") throw new ArgumentException("Invalid input mode");
            capture = new ActionCapture { engine_version = Application.unityVersion, action = action, revision = revision, source = source, input_mode = inputMode, input_description = inputDescription };
            counts.Clear(); startTime = Time.realtimeSinceStartupAsDouble; IsRecording = true; LastSavedPath = null;
        }
        public void RecordEvent(string track, string eventName, double uncertaintySeconds = 0) {
            if (!IsRecording) return;
            if (!Token.IsMatch(track ?? "") || !Token.IsMatch(eventName ?? "") || double.IsNaN(uncertaintySeconds) || double.IsInfinity(uncertaintySeconds) || uncertaintySeconds < 0) throw new ArgumentException("Invalid action event");
            if (capture.events.Count >= 10000) { capture.dropped_events++; return; }
            var key = track + "\n" + eventName;
            counts.TryGetValue(key, out int number); counts[key] = ++number;
            capture.events.Add(new RecordedEvent { track = track, id = eventName + "#" + number, t_s = Time.realtimeSinceStartupAsDouble - startTime, uncertainty_s = uncertaintySeconds });
        }
        // Use an Animation Event string such as "hand_contact"; rule events are recorded at the actual rule change.
        public void RecordAnimationEvent(string eventName) { RecordEvent("animation", eventName); }
        public string StopAndSave(bool complete = true) {
            if (!IsRecording) return LastSavedPath;
            capture.duration_s = Time.realtimeSinceStartupAsDouble - startTime; capture.complete = complete; IsRecording = false;
            var dir = Path.Combine(Application.persistentDataPath, "ActionTiming"); Directory.CreateDirectory(dir);
            var path = Path.Combine(dir, Guid.NewGuid().ToString("N") + ".json");
            using (var stream = new FileStream(path, FileMode.CreateNew))
            using (var writer = new StreamWriter(stream, new System.Text.UTF8Encoding(false))) writer.Write(JsonUtility.ToJson(capture, true));
            LastSavedPath = path; Debug.Log("ACTION_TIMING_SAVED " + path); return path;
        }
        private void OnDisable() { if (IsRecording) StopAndSave(false); }
    }
}
