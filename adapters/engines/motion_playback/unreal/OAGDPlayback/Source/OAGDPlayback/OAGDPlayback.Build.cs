using UnrealBuildTool;
public class OAGDPlayback : ModuleRules {
 public OAGDPlayback(ReadOnlyTargetRules Target) : base(Target) {
  PCHUsage=PCHUsageMode.UseExplicitOrSharedPCHs;
  PublicDependencyModuleNames.AddRange(new[]{"Core","CoreUObject","Engine","AnimGraphRuntime","Json"});
 }
}
