using UnrealBuildTool;
public class MotionPlayEditorTarget:TargetRules {public MotionPlayEditorTarget(TargetInfo Target):base(Target){Type=TargetType.Editor;DefaultBuildSettings=BuildSettingsVersion.Latest;IncludeOrderVersion=EngineIncludeOrderVersion.Unreal5_8;ExtraModuleNames.Add("MotionPlay");}}
