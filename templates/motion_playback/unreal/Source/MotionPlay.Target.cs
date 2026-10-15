using UnrealBuildTool;
public class MotionPlayTarget:TargetRules {public MotionPlayTarget(TargetInfo Target):base(Target){Type=TargetType.Game;DefaultBuildSettings=BuildSettingsVersion.Latest;IncludeOrderVersion=EngineIncludeOrderVersion.Unreal5_8;ExtraModuleNames.Add("MotionPlay");}}
