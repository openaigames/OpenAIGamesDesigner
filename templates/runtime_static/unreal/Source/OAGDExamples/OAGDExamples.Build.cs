using UnrealBuildTool;
public class OAGDExamples : ModuleRules {
 public OAGDExamples(ReadOnlyTargetRules Target) : base(Target) {
  PCHUsage=PCHUsageMode.UseExplicitOrSharedPCHs;
  PublicDependencyModuleNames.AddRange(new[]{"Core","CoreUObject","Engine","InputCore","OAGDCore","Json","Slate","SlateCore","NavigationSystem","ProceduralMeshComponent"});
  if(Target.bBuildEditor)PrivateDependencyModuleNames.Add("UnrealEd");
 }
}
