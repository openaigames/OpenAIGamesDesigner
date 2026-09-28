#include "AnimationLab.h"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/InputComponent.h"
#include "ProceduralMeshComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/PlayerController.h"
#include "Camera/CameraComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Json.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "DrawDebugHelpers.h"
#include "HAL/FileManager.h"
#include "UnrealClient.h"

namespace AnimationLabIO {
 TArray<TSharedPtr<FJsonValue>> Vec(FVector V){return {MakeShared<FJsonValueNumber>(V.X),MakeShared<FJsonValueNumber>(V.Y),MakeShared<FJsonValueNumber>(V.Z)};}
 FVector Vector(const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());}
 TSharedPtr<FJsonObject> Transform(FTransform T){auto O=MakeShared<FJsonObject>();O->SetArrayField(TEXT("p"),Vec(T.GetLocation()));const FQuat Q=T.GetRotation();O->SetArrayField(TEXT("q"),{MakeShared<FJsonValueNumber>(Q.X),MakeShared<FJsonValueNumber>(Q.Y),MakeShared<FJsonValueNumber>(Q.Z),MakeShared<FJsonValueNumber>(Q.W)});O->SetArrayField(TEXT("s"),Vec(T.GetScale3D()));return O;}
 FTransform Transform(const TSharedPtr<FJsonObject>& O){auto Q=O->GetArrayField(TEXT("q"));return FTransform(FQuat(Q[0]->AsNumber(),Q[1]->AsNumber(),Q[2]->AsNumber(),Q[3]->AsNumber()),Vector(O->GetArrayField(TEXT("p"))),Vector(O->GetArrayField(TEXT("s"))));}
 TSharedPtr<FJsonObject> Read(const FString& Path){FString S;TSharedPtr<FJsonObject> O;if(FFileHelper::LoadFileToString(S,*Path))FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S),O);return O;}
 bool Write(const FString& Path,const TSharedPtr<FJsonObject>& O){FString S;FJsonSerializer::Serialize(O.ToSharedRef(),TJsonWriterFactory<>::Create(&S));IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path),true);return FFileHelper::SaveStringToFile(S,*Path,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);}
 TArray<TSharedPtr<FJsonValue>> Bones(USkeletalMeshComponent* M){
  TArray<TSharedPtr<FJsonValue>> Out;const auto& R=M->GetSkeletalMeshAsset()->GetRefSkeleton();TArray<FTransform> World;
  for(int I=0;I<R.GetNum();I++){const int Parent=R.GetParentIndex(I);World.Add(Parent>=0?R.GetRefBonePose()[I]*World[Parent]:R.GetRefBonePose()[I]);auto B=MakeShared<FJsonObject>();B->SetStringField(TEXT("name"),R.GetBoneName(I).ToString());B->SetNumberField(TEXT("parent"),Parent);B->SetObjectField(TEXT("rest"),Transform(World[I]*M->GetRelativeTransform()));Out.Add(MakeShared<FJsonValueObject>(B));}return Out;
 }
 TSharedPtr<FJsonObject> Frame(USkeletalMeshComponent* M,USceneComponent* W,float T,const FTransform& Space){
  auto F=MakeShared<FJsonObject>();F->SetNumberField(TEXT("t"),T);TArray<TSharedPtr<FJsonValue>> Pose;
  for(int I=0;I<M->GetNumBones();I++)Pose.Add(MakeShared<FJsonValueObject>(Transform(M->GetBoneTransform(I).GetRelativeTransform(Space))));
  F->SetArrayField(TEXT("pose"),Pose);if(W)F->SetObjectField(TEXT("weapon"),Transform(W->GetComponentTransform().GetRelativeTransform(Space)));return F;
 }
}
using namespace AnimationLabIO;
AAnimationLabPawn::AAnimationLabPawn(){
 PrimaryActorTick.bCanEverTick=true;
 RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
 Body=CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Body"));Body->SetupAttachment(RootComponent);Body->SetRelativeRotation(FRotator(0,-90,0));Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);Body->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
 Weapon=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("Weapon"));Weapon->SetupAttachment(RootComponent);Weapon->SetVisibility(false);Weapon->SetCollisionEnabled(ECollisionEnabled::NoCollision);
 Boom=CreateDefaultSubobject<USpringArmComponent>(TEXT("Boom"));Boom->SetupAttachment(RootComponent);Boom->SetRelativeLocation(FVector(0,0,100));Boom->TargetArmLength=500;Boom->SetRelativeRotation(FRotator(-12,145,0));Boom->bDoCollisionTest=false;
 Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));Camera->SetupAttachment(Boom);Camera->FieldOfView=55;
}
void AAnimationLabPawn::BeginPlay(){
 Super::BeginPlay();
 if(!FParse::Value(FCommandLine::Get(),TEXT("AnimationLabManifest="),ManifestPath))ManifestPath=FPaths::ConvertRelativePathToFull(FPaths::ProjectDir()/TEXT("../manifest.json"));
 Manifest=Read(ManifestPath);if(!Manifest){Status=TEXT("MANIFEST LOAD FAILED");UE_LOG(LogTemp,Error,TEXT("ANIMLAB missing manifest %s"),*ManifestPath);return;}
 if(Manifest->GetStringField(TEXT("schema"))!=TEXT("animlab.manifest/1")){Status=TEXT("LEGACY LAB REQUIRES /1; USE CURRENT PROJECT CONSUMER FOR /2");UE_LOG(LogTemp,Error,TEXT("ANIMLAB legacy procedural weapon lab only supports /1; no implicit conversion"));return;}
 auto Rig=Manifest->GetObjectField(TEXT("rig"));Body->SetSkeletalMesh(LoadObject<USkeletalMesh>(nullptr,*Rig->GetStringField(TEXT("ue_mesh"))));Body->SetAnimationMode(EAnimationMode::AnimationSingleNode);Body->SetComponentTickEnabled(false);
 if(auto* Inspection=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/AnimationLab/Materials/M_Inspection.M_Inspection")))for(int I=0;I<Body->GetNumMaterials();I++)Body->SetMaterial(I,Inspection);
 Clips=Manifest->GetArrayField(TEXT("clips"));SelectClip(0);
 if(auto* PC=Cast<APlayerController>(Controller)){PC->bShowMouseCursor=false;PC->SetInputMode(FInputModeGameOnly());}
}
void AAnimationLabPawn::SelectClip(int Index){
 if(Clips.IsEmpty())return;ClipIndex=(Index%Clips.Num()+Clips.Num())%Clips.Num();auto C=Clips[ClipIndex]->AsObject();ClipID=C->GetStringField(TEXT("id"));WeaponID=C->GetStringField(TEXT("weapon"));
 Sequence=LoadObject<UAnimSequence>(nullptr,*C->GetStringField(TEXT("ue_asset")));
 if(!Sequence){Status=TEXT("ANIMATION NOT IMPORTED");return;}Body->SetAnimation(Sequence);Length=Sequence->GetPlayLength();Contact=C->GetObjectField(TEXT("timing"))->GetNumberField(TEXT("contact_s"));Time=0;ResetBinding();if(!bBindingValid)return;Sample(0);Status=TEXT("BASELINE / REVIEW REQUIRED");
}
void AAnimationLabPawn::ResetBinding(){
 bBindingValid=false;Weapon->SetVisibility(false);
 if(!Manifest||WeaponID.IsEmpty()){Status=TEXT("EXPLICIT BINDING MISSING");return;}
 const TSharedPtr<FJsonObject>* Weapons=nullptr;const TSharedPtr<FJsonObject>* Entry=nullptr;
 if(!Manifest->TryGetObjectField(TEXT("weapons"),Weapons)||!(*Weapons)->TryGetObjectField(WeaponID,Entry)){Status=TEXT("WEAPON CONFIG MISSING");return;}
 const auto W=*Entry;FString Parent;
 if(!W->TryGetStringField(TEXT("bone"),Parent)||Parent.IsEmpty()||!W->HasTypedField<EJson::Object>(TEXT("binding"))||!Body->DoesSocketExist(FName(*Parent))){Status=TEXT("ATTACHMENT MISSING / NO FALLBACK");UE_LOG(LogTemp,Error,TEXT("ANIMLAB explicit attachment missing: %s"),*Parent);return;}
 Binding=EditedBindings.Contains(WeaponID)?EditedBindings[WeaponID]:Transform(W->GetObjectField(TEXT("binding")));
 if(!Weapon->AttachToComponent(Body,FAttachmentTransformRules::KeepRelativeTransform,FName(*Parent))){Status=TEXT("ATTACH FAILED");return;}
 Weapon->SetRelativeTransform(Binding);BuildWeapon();bBindingValid=true;Weapon->SetVisibility(true);
}
void AAnimationLabPawn::BuildWeapon(){
 Weapon->ClearAllMeshSections();auto W=Manifest->GetObjectField(TEXT("weapons"))->GetObjectField(WeaponID);
 auto Sections=W->GetArrayField(TEXT("sections"));int S=0;
 for(auto& Section:Sections){auto O=Section->AsObject();TArray<FVector> V,N;TArray<int32> T;TArray<FVector2D> UV;TArray<FLinearColor>C;TArray<FProcMeshTangent> Tan;
  for(auto& A:O->GetArrayField(TEXT("vertices")))V.Add(Vector(A->AsArray()));for(auto& A:O->GetArrayField(TEXT("normals")))N.Add(Vector(A->AsArray()));for(auto& A:O->GetArrayField(TEXT("triangles")))T.Add(A->AsNumber());UV.Init(FVector2D::ZeroVector,V.Num());C.Init(FLinearColor::White,V.Num());Tan.Init(FProcMeshTangent(1,0,0),V.Num());Weapon->CreateMeshSection_LinearColor(S,V,T,N,UV,C,Tan,false);
  auto* Base=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/AnimationLab/Materials/M_Inspection.M_Inspection"));
  if(!Base)Base=LoadObject<UMaterialInterface>(nullptr,TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"));
  if(Base){auto* Mat=UMaterialInstanceDynamic::Create(Base,this);Mat->SetVectorParameterValue(TEXT("Tint"),S==1?FLinearColor(.045,.04,.035):S==2?(WeaponID==TEXT("hammer")?FLinearColor(.3,.16,.38):FLinearColor(.05,.32,.4)):FLinearColor(.3,.34,.38));Weapon->SetMaterial(S,Mat);}S++;
 }
}
void AAnimationLabPawn::Sample(float T){
 if(!Sequence||!bBindingValid)return;Time=FMath::Clamp(T,0.f,Length);
 auto C=Clips[ClipIndex]->AsObject();FString NewWeapon=C->GetStringField(TEXT("weapon"));
 const TArray<TSharedPtr<FJsonValue>>* Events=nullptr;if(C->TryGetArrayField(TEXT("weapon_events"),Events))for(auto& E:*Events){auto V=E->AsObject();if(V->GetNumberField(TEXT("t"))<=Time+.0001f)NewWeapon=V->GetStringField(TEXT("weapon"));}
 if(NewWeapon!=WeaponID){WeaponID=NewWeapon;ResetBinding();}
 Body->SetPosition(Time,false);Body->TickAnimation(0,false);Body->RefreshBoneTransforms();Body->UpdateComponentToWorld();Weapon->UpdateComponentToWorld();
}
void AAnimationLabPawn::BackFrame(){bPlaying=false;Sample(Time-1.f/60);}
void AAnimationLabPawn::ForwardFrame(){bPlaying=false;Sample(Time+1.f/60);}
void AAnimationLabPawn::CameraView(){View=(View+1)%3;Boom->SetRelativeRotation(View==0?FRotator(-12,145,0):View==1?FRotator(0,180,0):FRotator(0,90,0));}
void AAnimationLabPawn::Edit(int Axis,float Sign){
 if(!bBindingValid)return;
 auto* PC=Cast<APlayerController>(Controller);if(PC&&(PC->IsInputKeyDown(EKeys::LeftShift)||PC->IsInputKeyDown(EKeys::RightShift))){FRotator R=Binding.Rotator();if(Axis==0)R.Roll+=Sign*2;if(Axis==1)R.Pitch+=Sign*2;if(Axis==2)R.Yaw+=Sign*2;Binding.SetRotation(R.Quaternion());}
 else{FVector P=Binding.GetLocation();P[Axis]+=Sign;Binding.SetLocation(P);}Weapon->SetRelativeTransform(Binding);EditedBindings.Add(WeaponID,Binding);Status=TEXT("BINDING EDIT / PRESS B TO SAVE DRAFT");
}
void AAnimationLabPawn::SaveBinding(){auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("schema"),TEXT("animlab.binding-draft/1"));O->SetStringField(TEXT("weapon"),WeaponID);O->SetStringField(TEXT("manifest"),ManifestPath);O->SetObjectField(TEXT("source_manifest"),Manifest);O->SetObjectField(TEXT("binding"),Transform(Binding));const FString Path=FPaths::ProjectSavedDir()/TEXT("AnimationLab")/(WeaponID+TEXT("-binding-draft.json"));Status=Write(Path,O)?TEXT("DRAFT SAVED / RE-AUDIT BEFORE HANDOFF"):TEXT("DRAFT SAVE FAILED");}
void AAnimationLabPawn::SetupPlayerInputComponent(UInputComponent* I){
 Super::SetupPlayerInputComponent(I);
 I->BindKey(EKeys::SpaceBar,IE_Pressed,this,&AAnimationLabPawn::Pause);I->BindKey(EKeys::Q,IE_Pressed,this,&AAnimationLabPawn::Previous);I->BindKey(EKeys::E,IE_Pressed,this,&AAnimationLabPawn::Next);
 I->BindKey(EKeys::Left,IE_Pressed,this,&AAnimationLabPawn::BackFrame);I->BindKey(EKeys::Right,IE_Pressed,this,&AAnimationLabPawn::ForwardFrame);I->BindKey(EKeys::Comma,IE_Pressed,this,&AAnimationLabPawn::Slower);I->BindKey(EKeys::Period,IE_Pressed,this,&AAnimationLabPawn::Faster);
 I->BindKey(EKeys::C,IE_Pressed,this,&AAnimationLabPawn::CameraView);I->BindKey(EKeys::V,IE_Pressed,this,&AAnimationLabPawn::ToggleDebug);I->BindKey(EKeys::B,IE_Pressed,this,&AAnimationLabPawn::SaveBinding);I->BindKey(EKeys::R,IE_Pressed,this,&AAnimationLabPawn::RevertBinding);
 I->BindKey(EKeys::L,IE_Pressed,this,&AAnimationLabPawn::XP);I->BindKey(EKeys::J,IE_Pressed,this,&AAnimationLabPawn::XM);I->BindKey(EKeys::I,IE_Pressed,this,&AAnimationLabPawn::YP);I->BindKey(EKeys::K,IE_Pressed,this,&AAnimationLabPawn::YM);I->BindKey(EKeys::O,IE_Pressed,this,&AAnimationLabPawn::ZP);I->BindKey(EKeys::U,IE_Pressed,this,&AAnimationLabPawn::ZM);
}
void AAnimationLabPawn::Tick(float D){
 Super::Tick(D);if(bPlaying&&Sequence&&Length>0)Sample(FMath::Fmod(Time+D*Rate,Length));
 if(bDebug&&Manifest&&Sequence&&bBindingValid){auto W=Manifest->GetObjectField(TEXT("weapons"))->GetObjectField(WeaponID);
  for(auto& G:W->GetObjectField(TEXT("grips"))->Values){const FVector P=Weapon->GetComponentTransform().TransformPosition(Vector(G.Value->AsArray()));DrawDebugSphere(GetWorld(),P,3,8,FColor::Green,false,-1,0,.8f);}
  const float Range=Clips[ClipIndex]->AsObject()->GetNumberField(TEXT("test_distance_cm"));DrawDebugLine(GetWorld(),FVector(Range,-45,0),FVector(Range,45,0),FColor::Orange,false,-1,0,2);DrawDebugLine(GetWorld(),FVector(Range,0,0),FVector(Range,0,180),FColor::Orange,false,-1,0,2);
 }
}
void AAnimationLabHUD::DrawHUD(){
 Super::DrawHUD();auto* P=Cast<AAnimationLabPawn>(GetOwningPawn());if(!P||!Canvas)return;
 auto Text=[&](FString T,float X,float Y,float Size,FLinearColor Col){DrawText(T,Col,X,Y,GEngine->GetMediumFont(),Size,false);};
 const float W=Canvas->ClipX,H=Canvas->ClipY;DrawRect(FLinearColor(0,0,0,.7),0,0,W,110);
 Text(TEXT("ANIMATION LAB  /  NO COMBAT FX"),20,15,1.2,FLinearColor::White);Text(P->ClipID,20,42,1.1,FLinearColor(.1,.85,1));Text(P->Status,20,68,.85,FLinearColor(1,.65,.2));
 Text(FString::Printf(TEXT("FRAME %03d   %.3fs / %.3fs   x%.3g"),FMath::RoundToInt(P->Time*60),P->Time,P->Length,P->Rate),W-350,24,.9,FLinearColor::White);
 DrawRect(FLinearColor(0,0,0,.75),0,H-110,W,110);DrawRect(FLinearColor(.2,.3,.35),20,H-103,W-40,5);DrawRect(FLinearColor(.1,.85,1),20,H-103,(W-40)*P->Time/FMath::Max(.01f,P->Length),5);DrawRect(FLinearColor(1,.5,.1),20+(W-40)*P->Contact/FMath::Max(.01f,P->Length),H-108,2,16);
 Text(TEXT("Q/E  CLIP    SPACE  PAUSE    ARROWS  FRAME    ,/.  SPEED    C  VIEW    V  MARKERS"),20,H-86,.85,FLinearColor::White);
 Text(TEXT("J/L I/K U/O  GRIP XYZ    SHIFT + KEYS  ROTATE    B  SAVE DRAFT    R  RESET"),20,H-63,.8,FLinearColor::White);
 Text(FString::Printf(TEXT("GRIP %.1f %.1f %.1f cm   ROT %.1f %.1f %.1f"),P->Binding.GetLocation().X,P->Binding.GetLocation().Y,P->Binding.GetLocation().Z,P->Binding.Rotator().Roll,P->Binding.Rotator().Pitch,P->Binding.Rotator().Yaw),20,H-39,.8,FLinearColor(.5,.8,.9));
}
AAnimationLabMode::AAnimationLabMode(){DefaultPawnClass=AAnimationLabPawn::StaticClass();HUDClass=AAnimationLabHUD::StaticClass();PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickGroup=TG_PostUpdateWork;}
void AAnimationLabMode::BeginPlay(){Super::BeginPlay();FParse::Value(FCommandLine::Get(),TEXT("AnimationLabAudit="),AuditPath);FParse::Value(FCommandLine::Get(),TEXT("AnimationLabSelfTest="),SelfTestPath);if(!AuditPath.IsEmpty())Audit=MakeShared<FJsonObject>();bShowcase=FParse::Param(FCommandLine::Get(),TEXT("AnimationLabShowcase"));}
void AAnimationLabMode::Tick(float D){
 Super::Tick(D);auto* P=Cast<AAnimationLabPawn>(GetWorld()->GetFirstPlayerController()->GetPawn());if(!P||!P->Manifest)return;
 if(!SelfTestPath.IsEmpty()){
  auto Result=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> Checks;bool Passed=true;
  auto Check=[&](const FString& Name,bool OK){auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("name"),Name);O->SetBoolField(TEXT("passed"),OK);Checks.Add(MakeShared<FJsonValueObject>(O));Passed&=OK;};
  P->SelectClip(0);P->bPlaying=true;P->Pause();Check(TEXT("pause"),!P->bPlaying);
  P->Sample(0);P->ForwardFrame();Check(TEXT("advance_one_frame"),FMath::IsNearlyEqual(P->Time,1.f/60,.0001f));P->BackFrame();Check(TEXT("reverse_one_frame"),P->Time==0);
  P->Rate=1;P->Slower();P->Slower();Check(TEXT("quarter_speed"),P->Rate==.25f);P->Faster();Check(TEXT("increase_speed"),P->Rate==.5f);
  P->Previous();Check(TEXT("previous_wraps"),P->ClipIndex==P->Clips.Num()-1);P->Next();Check(TEXT("next_wraps"),P->ClipIndex==0);
  const FTransform Original=P->Binding;P->Edit(0,1);Check(TEXT("binding_edit_cm"),FMath::IsNearlyEqual(P->Binding.GetLocation().X,Original.GetLocation().X+1));P->Next();P->Previous();Check(TEXT("binding_persists_between_clips"),FMath::IsNearlyEqual(P->Binding.GetLocation().X,Original.GetLocation().X+1));
  P->SaveBinding();auto Draft=Read(FPaths::ProjectSavedDir()/TEXT("AnimationLab")/(P->WeaponID+TEXT("-binding-draft.json")));Check(TEXT("draft_saved_with_manifest"),Draft.IsValid()&&Draft->HasField(TEXT("source_manifest")));
  P->RevertBinding();Check(TEXT("reset_restores_binding"),P->Binding.Equals(Original,.0001f));const int OldView=P->View;P->CameraView();Check(TEXT("camera_cycles"),P->View==(OldView+1)%3);
  for(int I=0;I<P->Clips.Num();I++)if(P->Clips[I]->AsObject()->GetStringField(TEXT("id"))==TEXT("sword_to_hammer")){P->SelectClip(I);P->Sample(0);const FString First=P->WeaponID;P->Sample(P->Length);Check(TEXT("combo_switches_weapon"),First!=P->WeaponID);}
  Result->SetStringField(TEXT("scope"),TEXT("Native lab control handlers and real imported assets; not a human visual quality review"));Result->SetArrayField(TEXT("checks"),Checks);Result->SetBoolField(TEXT("passed"),Passed);bool Written=Write(SelfTestPath,Result);SelfTestPath.Empty();FPlatformMisc::RequestExitWithStatus(false,Passed&&Written?0:1);return;
 }
 if(bShowcase){
  P->bPlaying=false;P->bDebug=false;ScreenClock+=D;
  if(ScreenStep<5&&ScreenClock>2+ScreenStep*1.0f){
   const int Indices[]={0,3,7,7,9};const float Times[]={.12f,.44f,.4f,.62f,.9f};P->SelectClip(Indices[ScreenStep]);P->Sample(Times[ScreenStep]);P->Boom->SetRelativeRotation(ScreenStep%2?FRotator(-5,90,0):FRotator(-12,145,0));
   const FString Dir=FPaths::ConvertRelativePathToFull(FPaths::ProjectDir()/TEXT("../reports/unreal-frames"));IFileManager::Get().MakeDirectory(*Dir,true);FScreenshotRequest::RequestScreenshot(Dir/FString::Printf(TEXT("lab-%02d.png"),ScreenStep),true,false);ScreenStep++;
  }if(ScreenClock>8){UE_LOG(LogTemp,Display,TEXT("ANIMLAB_SHOWCASE_COMPLETE screenshots=%d"),ScreenStep);FPlatformMisc::RequestExit(false);}return;
 }
 if(AuditPath.IsEmpty())return;P->bPlaying=false;
 if(!P->Sequence||!P->bBindingValid){UE_LOG(LogTemp,Error,TEXT("ANIMLAB_AUDIT missing sequence or binding"));FPlatformMisc::RequestExitWithStatus(false,1);return;}
 if(AuditClip>=P->Clips.Num())return;
 P->Sample(FMath::Min(AuditFrame/60.f,P->Length));auto F=Frame(P->Body,P->Weapon,P->Time,P->GetActorTransform());F->SetStringField(TEXT("weapon_id"),P->WeaponID);Frames.Add(MakeShared<FJsonValueObject>(F));AuditFrame++;
 if((AuditFrame-1)/60.f>=P->Length){
  auto C=MakeShared<FJsonObject>(*P->Clips[AuditClip]->AsObject());C->SetArrayField(TEXT("frames"),Frames);C->SetNumberField(TEXT("duration_s"),P->Length);AuditClips.Add(MakeShared<FJsonValueObject>(C));Frames.Reset();AuditFrame=0;AuditClip++;
  if(AuditClip>=P->Clips.Num()){Audit->SetStringField(TEXT("schema"),TEXT("animlab.capture/1"));Audit->SetStringField(TEXT("stage"),TEXT("unreal_roundtrip"));Audit->SetArrayField(TEXT("bones"),Bones(P->Body));Audit->SetArrayField(TEXT("clips"),AuditClips);Audit->SetObjectField(TEXT("space"),P->Manifest->GetObjectField(TEXT("space")));bool OK=Write(AuditPath,Audit);UE_LOG(LogTemp,Display,TEXT("ANIMLAB_AUDIT_COMPLETE clips=%d"),AuditClips.Num());FPlatformMisc::RequestExitWithStatus(false,OK?0:1);}
  else P->SelectClip(AuditClip);
 }
}
