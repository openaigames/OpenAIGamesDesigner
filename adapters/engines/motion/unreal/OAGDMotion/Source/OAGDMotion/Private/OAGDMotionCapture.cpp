#include "OAGDMotionCapture.h"
#include "Modules/ModuleManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "Animation/AnimSequence.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/EngineVersion.h"
#include "Serialization/JsonSerializer.h"
#if ENGINE_MAJOR_VERSION != 5 || ENGINE_MINOR_VERSION != 8
#error OAGDMotion requires Unreal Engine 5.8
#endif
IMPLEMENT_MODULE(FDefaultModuleImpl, OAGDMotion)

static TSharedPtr<FJsonValue> Num(double V){return MakeShared<FJsonValueNumber>(V);}
AOAGDMotionCapture::AOAGDMotionCapture(){PrimaryActorTick.bCanEverTick=true;DefaultPawnClass=nullptr;}
void AOAGDMotionCapture::BeginPlay(){
    Super::BeginPlay();
    FString JobPath,Text;
    if(!FParse::Value(FCommandLine::Get(),TEXT("MotionJob="),JobPath)||!FFileHelper::LoadFileToString(Text,*JobPath)){Finish(TEXT("Missing MotionJob"));return;}
    TSharedPtr<FJsonObject> Job;
    auto Reader=TJsonReaderFactory<>::Create(Text);
    if(!FJsonSerializer::Deserialize(Reader,Job)||!Job.IsValid()){Finish(TEXT("Invalid MotionJob"));return;}
    FString MeshPath,AnimationPath;
    if(!Job->TryGetStringField(TEXT("report"),ReportPath)||!Job->TryGetStringField(TEXT("mesh"),MeshPath)||!Job->TryGetStringField(TEXT("animation"),AnimationPath)
      ||!Job->TryGetNumberField(TEXT("fps"),SampleRate)||!Job->TryGetNumberField(TEXT("frames"),SampleCount)||SampleRate<=0||SampleRate>240||SampleCount<2||SampleCount>100000){Finish(TEXT("Incomplete MotionJob"));return;}
    auto* Asset=LoadObject<USkeletalMesh>(nullptr,*MeshPath);Animation=LoadObject<UAnimSequence>(nullptr,*AnimationPath);
    if(!Asset||!Animation||Asset->GetSkeleton()!=Animation->GetSkeleton()){Finish(TEXT("Native animation/mesh unavailable or incompatible"));return;}
    auto* Actor=GetWorld()->SpawnActor<AActor>();Mesh=NewObject<USkeletalMeshComponent>(Actor);
    Actor->SetRootComponent(Mesh);Actor->AddInstanceComponent(Mesh);Mesh->RegisterComponent();Mesh->SetSkeletalMesh(Asset);
    Mesh->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);Mesh->PlayAnimation(Animation,false);Mesh->SetComponentTickEnabled(false);
}
void AOAGDMotionCapture::Tick(float DeltaSeconds){
    Super::Tick(DeltaSeconds);if(Finished||!Mesh)return;
    const double Time=SampleIndex/SampleRate;
    Mesh->SetPosition(Time,false);Mesh->TickAnimation(0,false);Mesh->RefreshBoneTransforms();Mesh->UpdateComponentToWorld();
    auto Bones=MakeShared<FJsonObject>();
    for(int32 I=0;I<Mesh->GetNumBones();++I){
        const FTransform T=Mesh->GetBoneTransform(I);const FVector P=T.GetLocation();const FQuat Q=T.GetRotation();
        auto Bone=MakeShared<FJsonObject>();Bone->SetArrayField(TEXT("p"),{Num(P.X),Num(P.Y),Num(P.Z)});Bone->SetArrayField(TEXT("q"),{Num(Q.X),Num(Q.Y),Num(Q.Z),Num(Q.W)});
        Bones->SetObjectField(Mesh->GetBoneName(I).ToString(),Bone);
    }
    auto Frame=MakeShared<FJsonObject>();Frame->SetNumberField(TEXT("t"),Time);Frame->SetNumberField(TEXT("animation_time"),Mesh->GetPosition());Frame->SetObjectField(TEXT("bones"),Bones);
    Samples.Add(MakeShared<FJsonValueObject>(Frame));++SampleIndex;if(SampleIndex>=SampleCount)Finish(TEXT(""));
}
void AOAGDMotionCapture::Finish(const FString& Error){
    Finished=true;auto Result=MakeShared<FJsonObject>();Result->SetBoolField(TEXT("ok"),Error.IsEmpty());Result->SetStringField(TEXT("error"),Error);
    Result->SetStringField(TEXT("engine"),TEXT("unreal"));Result->SetStringField(TEXT("engine_version"),FEngineVersion::Current().ToString());
    Result->SetStringField(TEXT("method"),TEXT("Native SingleNode animation, explicit seek, TickAnimation and RefreshBoneTransforms in a game world"));
    Result->SetStringField(TEXT("coordinates"),TEXT("UE_WORLD_CM"));Result->SetArrayField(TEXT("frames"),Samples);
    if(Animation)Result->SetNumberField(TEXT("length_s"),Animation->GetPlayLength());
    if(Animation)Result->SetStringField(TEXT("animation"),Animation->GetPathName());
    if(Mesh){Result->SetStringField(TEXT("mesh"),Mesh->GetSkeletalMeshAsset()->GetPathName());Result->SetArrayField(TEXT("root_bones"),{MakeShared<FJsonValueString>(Mesh->GetBoneName(0).ToString())});}
    FString Text;auto Writer=TJsonWriterFactory<>::Create(&Text);FJsonSerializer::Serialize(Result,Writer);
    const bool Saved=!ReportPath.IsEmpty()&&!FPaths::FileExists(ReportPath)&&FFileHelper::SaveStringToFile(Text,*ReportPath);
    FPlatformMisc::RequestExitWithStatus(true,(Error.IsEmpty()&&Saved)?0:2);
}
