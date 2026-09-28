using UnrealBuildTool;
public class ToolkitObservationTarget : TargetRules {
    public ToolkitObservationTarget(TargetInfo Target) : base(Target) {
        Type = TargetType.Game; DefaultBuildSettings = BuildSettingsVersion.Latest;
        ExtraModuleNames.Add("ToolkitObservation");
    }
}
