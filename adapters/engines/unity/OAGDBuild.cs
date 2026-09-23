// Shared Editor-only build operation for delivery and automated playback packages.
using UnityEditor;
using UnityEditor.Build.Reporting;

namespace OAGD {
    public static class PlayerBuild {
        public static BuildReport Run(string[] scenes, string output, BuildTarget target, bool development) {
            return BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes=scenes, locationPathName=output, target=target,
                options=development ? BuildOptions.Development : BuildOptions.None
            });
        }
    }
}
