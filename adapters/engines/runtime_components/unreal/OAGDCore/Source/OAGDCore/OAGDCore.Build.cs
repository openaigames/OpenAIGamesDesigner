using UnrealBuildTool;
public class OAGDCore : ModuleRules {
    public OAGDCore(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new [] {"Core", "CoreUObject", "Engine", "InputCore", "ProceduralMeshComponent", "Slate", "SlateCore", "Json"});
        PrivateDependencyModuleNames.AddRange(new [] {"ApplicationCore", "NavigationSystem"});
    }
}
