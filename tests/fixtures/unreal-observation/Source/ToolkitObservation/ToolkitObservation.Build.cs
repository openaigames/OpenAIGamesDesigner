using UnrealBuildTool;
public class ToolkitObservation : ModuleRules {
    public ToolkitObservation(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[]{"Core","CoreUObject","Engine","InputCore","Json"});
    }
}
