using UnrealBuildTool;
public class OAGDExamplesEditorTarget : TargetRules {
    public OAGDExamplesEditorTarget(TargetInfo Target) : base(Target) {
        Type=TargetType.Editor;
        DefaultBuildSettings=BuildSettingsVersion.Latest;
        IncludeOrderVersion=EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("OAGDExamples");
    }
}
