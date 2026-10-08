using UnrealBuildTool;
public class ActionTiming : ModuleRules {
    public ActionTiming(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new [] {"Core", "CoreUObject", "Engine", "Json"});
        PrivateDependencyModuleNames.AddRange(new [] {"Json"});
    }
}
