using UnrealBuildTool;
public class ToolkitObservationEditorTarget : TargetRules {
    public ToolkitObservationEditorTarget(TargetInfo Target) : base(Target) {
        Type = TargetType.Editor; DefaultBuildSettings = BuildSettingsVersion.Latest;
        ExtraModuleNames.Add("ToolkitObservation");
    }
}
