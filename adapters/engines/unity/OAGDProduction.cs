// Editor-only native production operations. Installed explicitly, never overwritten silently.
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Animations;
using UnityEngine.SceneManagement;

namespace OAGD {
[Serializable] public class ProductionProperty {
    public string name, kind, text, asset, object_path;
    public float number;
    public bool boolean;
    public float[] vector;
}
[Serializable] public class ProductionComponent {
    public string type;
    public ProductionProperty[] properties;
}
[Serializable] public class ProductionState { public string name, clip, clip_name; }
[Serializable] public class ProductionTransition { public string from, to, parameter; public float threshold, duration; public string condition; }
[Serializable] public class ProductionParameter { public string name, type; }
[Serializable] public class ProductionOperation {
    public string op, path, target, source, primitive, parent, animation_type, avatar, controller;
    public bool replace, create, loop;
    public float[] position, rotation, scale;
    public ProductionComponent[] components;
    public ProductionState[] states;
    public ProductionParameter[] parameters;
    public ProductionTransition[] transitions;
}
[Serializable] public class ProductionRequest {
    public string request_id, project, report, session, mode, scene;
    public ProductionOperation[] operations;
}
[Serializable] public class ProductionObject {
    public string path;
    public Vector3 position, rotation, scale;
    public string[] components, references;
}
[Serializable] public class ProductionResult {
    public bool success;
    public string engine="unity", request_id, project, version, error, scene;
    public List<string> completed = new List<string>();
    public List<ProductionObject> objects = new List<ProductionObject>();
}
public static class Production {
    static string Project { get { return Path.GetFullPath(Path.Combine(Application.dataPath,"..")); } }
    static string AssetPath(string value) {
        if (String.IsNullOrEmpty(value) || !value.StartsWith("Assets/",StringComparison.Ordinal)
            || !Path.GetFullPath(Path.Combine(Project,value)).StartsWith(Project+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)
            || value.Contains("..") || value.Contains("\\")) throw new Exception("Invalid project asset path: "+value);
        return value;
    }
    static void ParentDirectory(string path) { Directory.CreateDirectory(Path.GetDirectoryName(path)); AssetDatabase.Refresh(); }
    static Vector3 Vector(float[] a, Vector3 fallback) {
        if (a == null || a.Length == 0) return fallback;
        if (a.Length != 3 || a.Any(x=>Single.IsNaN(x)||Single.IsInfinity(x))) throw new Exception("Expected finite xyz vector");
        return new Vector3(a[0],a[1],a[2]);
    }
    static string ObjectPath(Transform obj) { return obj.parent == null ? obj.name : ObjectPath(obj.parent)+"/"+obj.name; }
    static GameObject Find(string value) {
        var matches = SceneManager.GetActiveScene().GetRootGameObjects()
            .SelectMany(g=>g.GetComponentsInChildren<Transform>(true)).Where(t=>ObjectPath(t)==value).ToArray();
        if(matches.Length!=1) throw new Exception("Object must resolve uniquely: "+value+" matches="+matches.Length);
        return matches[0].gameObject;
    }
    static UnityEngine.Object Asset(string value) {
        AssetPath(value);
        var a=AssetDatabase.LoadMainAssetAtPath(value);
        if(a==null) throw new Exception("Missing asset: "+value);
        return a;
    }
    static Type ComponentType(string name) {
        var types=AppDomain.CurrentDomain.GetAssemblies().Select(a=>a.GetType(name)).Where(t=>t!=null).Distinct().ToArray();
        if(types.Length!=1 || !typeof(Component).IsAssignableFrom(types[0])) throw new Exception("Unknown/ambiguous Component type: "+name);
        return types[0];
    }
    static void Properties(Component component, ProductionProperty[] values) {
        var so=new SerializedObject(component);
        foreach(var v in values ?? new ProductionProperty[0]) {
            var property=so.FindProperty(v.name);
            if(property==null) throw new Exception("Serialized property missing: "+component.GetType().Name+"."+v.name);
            switch(v.kind) {
                case "float": property.floatValue=v.number; break;
                case "int": property.intValue=checked((int)v.number); break;
                case "bool": property.boolValue=v.boolean; break;
                case "string": property.stringValue=v.text; break;
                case "vector3": property.vector3Value=Vector(v.vector,Vector3.zero); break;
                case "enum":
                    int index=Array.IndexOf(property.enumNames,v.text);
                    if(index<0) throw new Exception("Unknown enum: "+v.text);
                    property.enumValueIndex=index; break;
                case "asset": property.objectReferenceValue=Asset(v.asset); break;
                case "object": property.objectReferenceValue=Find(v.object_path); break;
                default: throw new Exception("Unsupported property kind: "+v.kind);
            }
        }
        so.ApplyModifiedPropertiesWithoutUndo(); EditorUtility.SetDirty(component);
    }
    static void Apply(ProductionOperation op) {
        if(op.op=="scene") {
            string path=AssetPath(op.path);
            if(!path.EndsWith(".unity")) throw new Exception("Scene path must end in .unity");
            if(op.create) {
                if(File.Exists(path)) throw new Exception("Scene already exists");
                ParentDirectory(path);
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
                if(!EditorSceneManager.SaveScene(SceneManager.GetActiveScene(),path)) throw new Exception("Scene save failed");
            } else EditorSceneManager.OpenScene(path,OpenSceneMode.Single);
        } else if(op.op=="object") {
            GameObject obj;
            if(op.create) {
                if(String.IsNullOrEmpty(op.target) || op.target.Contains("/")) throw new Exception("New object target must be a single name; use parent separately");
                string full=String.IsNullOrEmpty(op.parent)?op.target:op.parent+"/"+op.target;
                if(SceneManager.GetActiveScene().GetRootGameObjects().SelectMany(g=>g.GetComponentsInChildren<Transform>(true)).Any(t=>ObjectPath(t)==full))
                    throw new Exception("Object already exists: "+full);
                if(!String.IsNullOrEmpty(op.source)) obj=(GameObject)PrefabUtility.InstantiatePrefab(Asset(op.source));
                else if(!String.IsNullOrEmpty(op.primitive)) obj=GameObject.CreatePrimitive((PrimitiveType)Enum.Parse(typeof(PrimitiveType),op.primitive));
                else obj=new GameObject();
                obj.name=op.target;
                if(!String.IsNullOrEmpty(op.parent)) obj.transform.SetParent(Find(op.parent).transform,false);
            } else obj=Find(op.target);
            obj.transform.localPosition=Vector(op.position,obj.transform.localPosition);
            obj.transform.localEulerAngles=Vector(op.rotation,obj.transform.localEulerAngles);
            obj.transform.localScale=Vector(op.scale,obj.transform.localScale);
            foreach(var c in op.components ?? new ProductionComponent[0]) {
                Type type=ComponentType(c.type);
                var existing=obj.GetComponents(type);
                if(existing.Length>1) throw new Exception("Ambiguous component: "+c.type);
                var component=existing.Length==1?existing[0]:obj.AddComponent(type);
                Properties(component,c.properties);
            }
            EditorUtility.SetDirty(obj);
        } else if(op.op=="import") {
            string path=AssetPath(op.path);
            if(!File.Exists(op.source)) throw new Exception("Import source missing");
            if(File.Exists(path) && !op.replace) throw new Exception("Import destination exists; replace must be explicit");
            ParentDirectory(path); File.Copy(op.source,path,op.replace);
            AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);
            Asset(path); // Ensure engine recognition, not just a file copy.
        } else if(op.op=="model") {
            var importer=AssetImporter.GetAtPath(AssetPath(op.path)) as ModelImporter;
            if(importer==null) throw new Exception("Not a model importer");
            if(!String.IsNullOrEmpty(op.animation_type)) importer.animationType=(ModelImporterAnimationType)Enum.Parse(typeof(ModelImporterAnimationType),op.animation_type);
            if(!String.IsNullOrEmpty(op.avatar)) {
                var avatar=AssetDatabase.LoadAllAssetsAtPath(AssetPath(op.avatar)).OfType<Avatar>().SingleOrDefault();
                if(avatar==null || !avatar.isValid) throw new Exception("Missing/invalid source avatar");
                importer.sourceAvatar=avatar; importer.avatarSetup=ModelImporterAvatarSetup.CopyFromOther;
            }
            importer.SaveAndReimport();
        } else if(op.op=="animation") {
            string path=AssetPath(op.controller);
            if(AssetDatabase.LoadMainAssetAtPath(path)!=null) throw new Exception("Controller exists; edit it separately rather than overwriting states");
            ParentDirectory(path);
            var controller=AnimatorController.CreateAnimatorControllerAtPath(path);
            var machine=controller.layers[0].stateMachine;
            var states=new Dictionary<string,AnimatorState>();
            foreach(var parameter in op.parameters ?? new ProductionParameter[0])
                controller.AddParameter(parameter.name,(AnimatorControllerParameterType)Enum.Parse(typeof(AnimatorControllerParameterType),parameter.type));
            foreach(var state in op.states ?? new ProductionState[0]) {
                var clips=AssetDatabase.LoadAllAssetsAtPath(AssetPath(state.clip)).OfType<AnimationClip>()
                    .Where(c=>!c.name.StartsWith("__preview__") && (String.IsNullOrEmpty(state.clip_name)||c.name==state.clip_name)).ToArray();
                if(clips.Length!=1) throw new Exception("Choose an exact clip_name for "+state.clip);
                var s=machine.AddState(state.name); s.motion=clips[0]; states.Add(state.name,s);
                if(states.Count==1) machine.defaultState=s;
            }
            if(states.Count==0) throw new Exception("Animation controller requires states");
            foreach(var transition in op.transitions ?? new ProductionTransition[0]) {
                var t=states[transition.from].AddTransition(states[transition.to]);
                t.duration=transition.duration; t.hasExitTime=String.IsNullOrEmpty(transition.parameter);
                if(!t.hasExitTime) t.AddCondition((AnimatorConditionMode)Enum.Parse(typeof(AnimatorConditionMode),transition.condition),transition.threshold,transition.parameter);
            }
            var obj=Find(op.target); var animator=obj.GetComponent<Animator>();
            if(animator==null) animator=obj.AddComponent<Animator>(); // Unity's native fake-null must use ==.
            animator.runtimeAnimatorController=controller;
            if(!String.IsNullOrEmpty(op.avatar)) {
                var avatar=AssetDatabase.LoadAllAssetsAtPath(AssetPath(op.avatar)).OfType<Avatar>().SingleOrDefault();
                if(avatar==null || !avatar.isValid) throw new Exception("Missing/invalid avatar");
                animator.avatar=avatar;
            }
            EditorUtility.SetDirty(animator);
        } else throw new Exception("Unsupported Unity operation: "+op.op);
    }
    static void Inspect(ProductionResult result) {
        result.scene=SceneManager.GetActiveScene().path;
        foreach(var obj in SceneManager.GetActiveScene().GetRootGameObjects().SelectMany(g=>g.GetComponentsInChildren<Transform>(true))) {
            var references=new List<string>();
            foreach(var component in obj.GetComponents<Component>()) {
                if(component==null) throw new Exception("Missing script component on "+ObjectPath(obj));
                var so=new SerializedObject(component); var iterator=so.GetIterator();
                while(iterator.Next(true)) {
                    if(iterator.propertyType==SerializedPropertyType.ObjectReference && iterator.objectReferenceValue!=null) {
                        string asset=AssetDatabase.GetAssetPath(iterator.objectReferenceValue);
                        if(!String.IsNullOrEmpty(asset)) references.Add(component.GetType().FullName+"."+iterator.propertyPath+"="+asset);
                    }
                }
            }
            result.objects.Add(new ProductionObject { path=ObjectPath(obj),position=obj.localPosition,rotation=obj.localEulerAngles,
                scale=obj.localScale,components=obj.GetComponents<Component>().Select(c=>c.GetType().FullName).ToArray(),references=references.ToArray() });
        }
    }
    public static void Execute() {
        string[] args=Environment.GetCommandLineArgs(); int index=Array.IndexOf(args,"-oagdRequest");
        if(index<0 || index+1>=args.Length) throw new Exception("Missing -oagdRequest");
        var request=JsonUtility.FromJson<ProductionRequest>(File.ReadAllText(args[index+1]));
        var result=new ProductionResult { request_id=request.request_id,project=Project,version=Application.unityVersion };
        try {
            if(!String.Equals(Path.GetFullPath(request.project),Project,StringComparison.OrdinalIgnoreCase)) throw new Exception("Project identity mismatch");
            if(!String.IsNullOrEmpty(request.scene)) EditorSceneManager.OpenScene(AssetPath(request.scene),OpenSceneMode.Single);
            if(request.mode=="playback") {
                if(String.IsNullOrEmpty(request.scene)) throw new Exception("Playback requires a saved scene");
                var output=Path.Combine(request.session,"player/Playback.exe"); Directory.CreateDirectory(Path.GetDirectoryName(output));
                var build=PlayerBuild.Run(new[]{request.scene}, output, BuildTarget.StandaloneWindows64, true);
                if(build.summary.result!=UnityEditor.Build.Reporting.BuildResult.Succeeded) throw new Exception("Playback build failed: "+build.summary.result);
            } else {
                if(request.mode!="edit" && request.mode!="inspect") throw new Exception("Unsupported mode");
                if(request.mode=="inspect" && request.operations!=null && request.operations.Length>0) throw new Exception("Inspect does not execute mutations");
                foreach(var op in request.operations ?? new ProductionOperation[0]) { Apply(op); result.completed.Add(op.op+":"+(op.target??op.path)); }
                if(request.mode=="edit") {
                    AssetDatabase.SaveAssets();
                    var scene=SceneManager.GetActiveScene();
                    if(String.IsNullOrEmpty(scene.path)) throw new Exception("Changes require an explicit saved scene");
                    EditorSceneManager.MarkSceneDirty(scene);
                    if(!EditorSceneManager.SaveScene(scene)) throw new Exception("Scene save failed");
                    EditorSceneManager.OpenScene(scene.path,OpenSceneMode.Single);
                }
                Inspect(result);
            }
            result.success=true;
        } catch(Exception error) { result.error=error.ToString(); Debug.LogError(error); }
        File.WriteAllText(request.report,JsonUtility.ToJson(result,true));
        if(!result.success) EditorApplication.Exit(1);
    }
}
}
