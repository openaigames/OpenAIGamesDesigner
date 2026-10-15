using UnrealBuildTool;
public class OAGDExamples : ModuleRules {
    public OAGDExamples(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage=PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new [] {"Core","CoreUObject","Engine","InputCore","OAGDCore"});
        PrivateDependencyModuleNames.AddRange(new [] {"Json"});
    }
}
