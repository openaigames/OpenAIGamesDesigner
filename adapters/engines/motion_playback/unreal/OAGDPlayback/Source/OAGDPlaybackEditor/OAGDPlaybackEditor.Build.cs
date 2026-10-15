using UnrealBuildTool;
public class OAGDPlaybackEditor : ModuleRules {
 public OAGDPlaybackEditor(ReadOnlyTargetRules Target):base(Target) {
  PCHUsage=PCHUsageMode.UseExplicitOrSharedPCHs;
  PublicDependencyModuleNames.AddRange(new[]{"Core","CoreUObject","Engine","OAGDPlayback"});
  PrivateDependencyModuleNames.AddRange(new[]{"UnrealEd","AnimGraph","AnimGraphRuntime","BlueprintGraph","Kismet","KismetCompiler"});
 }
}
