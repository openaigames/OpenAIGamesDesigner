using UnrealBuildTool;
public class OAGDExamplesTarget : TargetRules {
    public OAGDExamplesTarget(TargetInfo Target) : base(Target) {
        Type=TargetType.Game;
        DefaultBuildSettings=BuildSettingsVersion.Latest;
        IncludeOrderVersion=EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("OAGDExamples");
    }
}
