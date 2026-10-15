using UnrealBuildTool;
public class OAGDMotion : ModuleRules {
    public OAGDMotion(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage=PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new [] {"Core","CoreUObject","Engine"});
        PrivateDependencyModuleNames.Add("Json");
    }
}
