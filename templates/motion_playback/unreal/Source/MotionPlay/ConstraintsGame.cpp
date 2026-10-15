#include "ConstraintsGame.h"
#include "Components/InputComponent.h"
#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Engine/World.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/DirectionalLight.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/EngineVersion.h"
#include "Serialization/JsonSerializer.h"
#include "HAL/FileManager.h"
#include "UnrealClient.h"
static const TArray<FString> Cases={TEXT("flat"),TEXT("slope"),TEXT("step_up"),TEXT("step_down"),TEXT("air_land"),TEXT("swing"),TEXT("no_ground"),TEXT("steep"),TEXT("high_step"),TEXT("single_hand"),TEXT("two_hand"),TEXT("carry"),TEXT("turn"),TEXT("switch"),TEXT("cancel"),TEXT("drop"),TEXT("lost_target"),TEXT("unreachable"),TEXT("regrab"),TEXT("feet_only"),TEXT("grip_only"),TEXT("foot_reach")};
static TSharedPtr<FJsonValue> Num(double X){return MakeShared<FJsonValueNumber>(X);}
static TArray<TSharedPtr<FJsonValue>> Vec(FVector P){return {Num(P.X/100),Num(P.Y/100),Num(P.Z/100)};}
static AStaticMeshActor* Box(UWorld* World,FVector P,FVector Size,FLinearColor Color){
 auto* A=World->SpawnActor<AStaticMeshActor>(P,FRotator::ZeroRotator);auto* M=A->GetStaticMeshComponent();M->SetMobility(EComponentMobility::Movable);M->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));A->SetActorScale3D(Size/100);
 auto* Material=UMaterialInstanceDynamic::Create(LoadObject<UMaterial>(nullptr,TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")),A);Material->SetVectorParameterValue(TEXT("Color"),Color);M->SetMaterial(0,Material);M->SetCollisionProfileName(TEXT("BlockAll"));return A;
}
AConstraintsPlayer::AConstraintsPlayer(){
 PrimaryActorTick.bCanEverTick=true;Motion=CreateDefaultSubobject<UOAGDPlaybackComponent>(TEXT("Motion"));IK=CreateDefaultSubobject<UOAGDConstraintsComponent>(TEXT("Contacts"));GetMesh()->SetRelativeLocation(FVector(0,0,-90));GetMesh()->SetRelativeRotation(FRotator(0,-90,0));GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;GetMesh()->bEnableUpdateRateOptimizations=false;
 auto* M=GetCharacterMovement();M->bTickBeforeOwner=false;M->bOrientRotationToMovement=false;M->MaxWalkSpeed=35;M->JumpZVelocity=380;M->MaxAcceleration=10000;M->BrakingDecelerationWalking=10000;
 CameraArm->bInheritYaw=false;CameraArm->bDoCollisionTest=false;CameraArm->TargetArmLength=380;CameraArm->TargetOffset=FVector(0,0,0);CameraArm->SetRelativeRotation(FRotator(-18,140,0));
 FollowCamera->SetFieldOfView(65);
}
void AConstraintsPlayer::BeginPlay(){
 Super::BeginPlay();GetCharacterMovement()->AddTickPrerequisiteActor(this);FParse::Value(FCommandLine::Get(),TEXT("MotionReport="),Output);FParse::Value(FCommandLine::Get(),TEXT("MotionFrames="),FramesDirectory);FParse::Value(FCommandLine::Get(),TEXT("MotionView="),View);if(!FramesDirectory.IsEmpty())IFileManager::Get().MakeDirectory(*FramesDirectory,true);
 FString Content=TEXT("/Game/Playback");GConfig->GetString(TEXT("OAGDPlayback"),TEXT("RevisionRoot"),Content,GGameIni);GetMesh()->SetSkeletalMesh(LoadObject<USkeletalMesh>(nullptr,*(Content/TEXT("idle/idle.idle"))));Motion->Bindings=LoadObject<UOAGDPlaybackSet>(nullptr,*(Content/TEXT("Bindings.Bindings")));GetMesh()->SetAnimInstanceClass(LoadClass<UAnimInstance>(nullptr,*(Content/TEXT("ABP_Player.ABP_Player_C"))));
 if(!Motion->Bindings||!IK->Configure(GetMesh(),Motion->Bindings->ConstraintsJson)){UE_LOG(LogTemp,Error,TEXT("Contacts rejected"));FGenericPlatformMisc::RequestExitWithStatus(false,3);return;}Original=IK->Settings;
 for(const FString Kind:{TEXT("missing_bone"),TEXT("broken_chain"),TEXT("zero_blend"),TEXT("bad_socket")}){
  TSharedPtr<FJsonObject> Bad;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Motion->Bindings->ConstraintsJson),Bad);
  if((Kind==TEXT("bad_socket")&&!Original.Grip)||(Kind!=TEXT("bad_socket")&&!Original.Feet))continue;
  auto Feet=Original.Feet?Bad->GetObjectField(TEXT("feet")):MakeShared<FJsonObject>();
  if(Kind==TEXT("missing_bone"))Feet->SetStringField(TEXT("pelvis"),TEXT("absent"));
  if(Kind==TEXT("broken_chain")){auto A=Feet->GetArrayField(TEXT("left"));Swap(A[0],A[2]);Feet->SetArrayField(TEXT("left"),A);}
  if(Kind==TEXT("zero_blend"))Feet->SetNumberField(TEXT("blend_s"),0);
  if(Kind==TEXT("bad_socket"))Bad->GetObjectField(TEXT("grip"))->GetObjectField(TEXT("sockets"))->GetObjectField(TEXT("unreal"))->GetObjectField(TEXT("main"))->SetArrayField(TEXT("rotation_xyzw"),{Num(0),Num(0),Num(0),Num(2)});
  FString Text;FJsonSerializer::Serialize(Bad.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));auto* Test=NewObject<UOAGDConstraintsComponent>(this);const bool Rejected=!Test->Configure(GetMesh(),Text);Test->DestroyComponent();
  auto E=MakeShared<FJsonObject>();E->SetStringField(TEXT("kind"),TEXT("config_rejected"));E->SetStringField(TEXT("name"),Kind);E->SetBoolField(TEXT("ok"),Rejected);Events.Add(MakeShared<FJsonValueObject>(E));
 }
 {auto E=MakeShared<FJsonObject>();E->SetStringField(TEXT("kind"),TEXT("missing_request_rejected"));E->SetBoolField(TEXT("ok"),!IK->Take(nullptr));Events.Add(MakeShared<FJsonValueObject>(E));}
 Floor=Box(GetWorld(),FVector(0,0,-10),FVector(2000,2000,20),FLinearColor(.2,.28,.38));Platform=Box(GetWorld(),FVector(0,100,6),FVector(300,200,12),FLinearColor(.46,.38,.25));Platform->GetStaticMeshComponent()->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);
 NextCase();Observer=FWorldDelegates::OnWorldPostActorTick.AddUObject(this,&AConstraintsPlayer::Observe);
}
void AConstraintsPlayer::EndPlay(const EEndPlayReason::Type Reason){FWorldDelegates::OnWorldPostActorTick.Remove(Observer);Super::EndPlay(Reason);}
void AConstraintsPlayer::SetupPlayerInputComponent(UInputComponent* Input){Super::SetupPlayerInputComponent(Input);Input->BindAxis(TEXT("Forward"),this,&AConstraintsPlayer::Forward);Input->BindAxis(TEXT("Right"),this,&AConstraintsPlayer::Right);Input->BindKey(EKeys::E,IE_Pressed,this,&AConstraintsPlayer::PickUp);Input->BindKey(EKeys::Q,IE_Pressed,this,&AConstraintsPlayer::Drop);Input->BindKey(EKeys::SpaceBar,IE_Pressed,this,&AConstraintsPlayer::Hop);}
void AConstraintsPlayer::Forward(float V){Wish.X=V;}void AConstraintsPlayer::Right(float V){Wish.Y=V;}void AConstraintsPlayer::PickUp(){Motion->Select(TEXT("hold"));Take();}void AConstraintsPlayer::Drop(){IK->Release();Motion->Select(TEXT("idle"));}void AConstraintsPlayer::Hop(){Jump();}
FString AConstraintsPlayer::CaseName()const{return Cases.IsValidIndex(CaseIndex)?Cases[CaseIndex]:TEXT("interactive");}
void AConstraintsPlayer::NextCase(){
 ++CaseIndex;Clock=0;Steps.Empty();IK->Reset();IK->Settings=Original;if(IsValid(Prop))Prop->Destroy();Prop=Box(GetWorld(),FVector(50,0,100),FVector(8,38,6),FLinearColor(.84,.6,.22));Prop->SetActorEnableCollision(false);
 ResetMotor(FVector(0,0,93));SetActorRotation(FRotator::ZeroRotator);Floor->SetActorRotation(FRotator::ZeroRotator);Floor->GetStaticMeshComponent()->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);Platform->SetActorEnableCollision(false);Platform->SetActorHiddenInGame(true);
 Platform->SetActorRotation(FRotator::ZeroRotator);Platform->SetActorLocation(FVector(0,100,6));
 const FString Name=CaseName();if(Name==TEXT("slope"))Floor->SetActorRotation(FRotator(0,0,12));
 if(Name==TEXT("steep")){Floor->GetStaticMeshComponent()->SetCollisionResponseToChannel(ECC_Visibility,ECR_Ignore);Platform->SetActorEnableCollision(true);Platform->SetActorHiddenInGame(false);Platform->SetActorLocation(FVector(0,0,-10));Platform->SetActorRotation(FRotator(0,0,55));}
 if(Name==TEXT("step_up")||Name==TEXT("step_down")||Name==TEXT("high_step")){Platform->SetActorEnableCollision(true);Platform->SetActorHiddenInGame(false);Platform->SetActorLocation(FVector(0,100,Name==TEXT("high_step")?34:6));if(Name==TEXT("step_down"))SetActorLocation(FVector(0,0,105));}
 IK->Settings.Feet=Original.Feet&&Name!=TEXT("grip_only");IK->Settings.Grip=Original.Grip&&Name!=TEXT("feet_only");Motion->Select(TEXT("idle"));Motion->SetRate(1);
 if(Name==TEXT("foot_reach"))IK->Settings.MaxPelvis=0;
 if(Name==TEXT("step_down")||Name==TEXT("foot_reach"))GetCharacterMovement()->DisableMovement(); // fixed-height probe fixtures; prevent CMC floor snap
}
void AConstraintsPlayer::Take(bool Both){bool Ok=IK->Take(IsValid(Prop)?Prop->GetStaticMeshComponent():nullptr,Both);auto E=MakeShared<FJsonObject>();E->SetStringField(TEXT("case"),CaseName());E->SetNumberField(TEXT("t"),Clock);E->SetStringField(TEXT("kind"),TEXT("take"));E->SetBoolField(TEXT("ok"),Ok);Events.Add(MakeShared<FJsonValueObject>(E));}
void AConstraintsPlayer::Tick(float Delta){
 Super::Tick(Delta);if(!IK->Valid)return;Clock+=Delta;const FString Name=CaseName();auto Once=[&](FString Key,float At,TFunction<void()> Call){if(Clock>=At&&!Steps.Contains(Key)){Steps.Add(Key);Call();}};
 if(!Output.IsEmpty()){
  Wish=FVector2D::ZeroVector;if(IK->Settings.Grip&&CaseIndex>=9&&Name!=TEXT("feet_only")&&Name!=TEXT("foot_reach")){
   Once(TEXT("pose"),.1,[&]{Motion->Select(TEXT("hold"));});Once(TEXT("take"),.35,[&]{Take(Name!=TEXT("single_hand"));});
   if(Name==TEXT("carry")){Wish=FVector2D(1,0);Once(TEXT("carry"),.7,[&]{Motion->Select(TEXT("carry"));});}
   if(Name==TEXT("turn"))SetActorRotation(FRotator(0,FMath::RadiansToDegrees(FMath::Clamp((Clock-.7f)*1.3f,0.f,PI)),0));
   if(Name==TEXT("switch"))Once(TEXT("switch"),.9,[&]{Motion->Select(TEXT("carry"));});
   if(Name==TEXT("cancel")||Name==TEXT("drop")||Name==TEXT("regrab"))Once(TEXT("drop"),1.1,[&]{IK->Release();});
   if(Name==TEXT("regrab"))Once(TEXT("regrab"),1.45,[&]{Take();});
   if(Name==TEXT("lost_target"))Once(TEXT("lost"),1.1,[&]{Prop->Destroy();});
   if(Name==TEXT("unreachable")){auto T=Original.SupportSocket;T.AddToTranslation(FVector(500,0,0));IK->Settings.SupportSocket=T;}
  }
  if(Name==TEXT("air_land"))Once(TEXT("jump"),.5,[&]{Hop();});
  if(Name==TEXT("no_ground"))Floor->GetStaticMeshComponent()->SetCollisionResponseToChannel(ECC_Visibility,ECR_Ignore);
 }
 MoveWorld(Wish);if(Name==TEXT("step_down")){auto P=GetActorLocation();P.Z=102;SetActorLocation(P);}
 if(Name==TEXT("foot_reach")){auto P=GetActorLocation();P.Z=112;SetActorLocation(P);}
 FVector2D Stance(1,1);if(Name==TEXT("swing")&&Clock>.5&&Clock<1.4)Stance.X=0;
 if((Name==TEXT("carry")||Name==TEXT("switch"))&&Motion->Current()==TEXT("carry")){float Phase=FMath::Fmod(Motion->PositionSeconds,1);Stance=FVector2D(Phase>.1&&Phase<.4?1:0,Phase>.6&&Phase<.9?1:0);}
 IK->Prepare(Delta,GetCharacterMovement()->IsMovingOnGround()||Name==TEXT("step_down")||Name==TEXT("foot_reach"),Stance,Clock>=.5&&Clock<1.8);
 if(View==TEXT("side")||View==TEXT("front")){CameraArm->TargetArmLength=400;CameraArm->SetRelativeRotation(FRotator(-5,View==TEXT("side")?-90:180,0));}
}
void AConstraintsPlayer::Observe(UWorld* World,ELevelTick Type,float Delta){
 if(World!=GetWorld()||Output.IsEmpty()||!IK->Valid)return;const auto& R=IK->Result;
 auto F=MakeShared<FJsonObject>();F->SetStringField(TEXT("case"),CaseName());F->SetNumberField(TEXT("t"),Clock);F->SetNumberField(TEXT("dt"),Delta);F->SetArrayField(TEXT("actor"),Vec(GetActorLocation()-FVector(0,0,90)));F->SetBoolField(TEXT("grounded"),GetCharacterMovement()->IsMovingOnGround());F->SetStringField(TEXT("state"),Motion->Current().ToString());F->SetNumberField(TEXT("clock"),Motion->PositionSeconds);
 auto Bones=MakeShared<FJsonObject>();for(int I=0;I<GetMesh()->GetNumBones();++I){FName Name=GetMesh()->GetBoneName(I);Bones->SetArrayField(Name.ToString(),Vec(GetMesh()->GetSocketLocation(Name)));}F->SetObjectField(TEXT("bones"),Bones);
 auto Q=GetMesh()->GetSocketTransform(Original.Main).GetRotation();F->SetArrayField(TEXT("main_quaternion_native"),{Num(Q.X),Num(Q.Y),Num(Q.Z),Num(Q.W)});
 if(Original.Grip){Q=GetMesh()->GetSocketTransform(Original.Offhand[2]).GetRotation();F->SetArrayField(TEXT("off_quaternion_native"),{Num(Q.X),Num(Q.Y),Num(Q.Z),Num(Q.W)});}
 const auto Forward=GetActorForwardVector();F->SetArrayField(TEXT("forward"),{Num(Forward.X),Num(Forward.Y),Num(Forward.Z)});
 F->SetArrayField(TEXT("feet_status"),{MakeShared<FJsonValueString>(R.FeetStatus[0]),MakeShared<FJsonValueString>(R.FeetStatus[1])});F->SetArrayField(TEXT("weights"),{Num(R.Weights.X),Num(R.Weights.Y)});F->SetNumberField(TEXT("pelvis"),R.Pelvis/100);F->SetArrayField(TEXT("goals"),{MakeShared<FJsonValueArray>(Vec(R.Goals[0])),MakeShared<FJsonValueArray>(Vec(R.Goals[1]))});F->SetStringField(TEXT("grip_status"),R.GripStatus);F->SetNumberField(TEXT("grip_weight"),R.GripWeight);F->SetBoolField(TEXT("holding"),IK->Holding);F->SetArrayField(TEXT("support"),Vec(R.Support.GetLocation()));F->SetArrayField(TEXT("prop"),IsValid(Prop)?Vec(Prop->GetActorLocation()):TArray<TSharedPtr<FJsonValue>>());Frames.Add(MakeShared<FJsonValueObject>(F));
 if(!FramesDirectory.IsEmpty()&&FrameIndex%12==0)FScreenshotRequest::RequestScreenshot(FramesDirectory/FString::Printf(TEXT("frame_%05d.png"),FrameIndex),false,false);++FrameIndex;
 if(Clock>=2.2){if(CaseIndex+1==Cases.Num()){auto Report=MakeShared<FJsonObject>();Report->SetStringField(TEXT("schema"),TEXT("oagd.constraints-runtime/1"));Report->SetStringField(TEXT("engine"),FEngineVersion::Current().ToString());Report->SetArrayField(TEXT("frames"),Frames);Report->SetArrayField(TEXT("events"),Events);FString Text;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*Output);FGenericPlatformMisc::RequestExit(false);}else NextCase();}
}
AConstraintsGame::AConstraintsGame(){DefaultPawnClass=AConstraintsPlayer::StaticClass();HUDClass=AConstraintsHUD::StaticClass();}
void AConstraintsGame::BeginPlay(){Super::BeginPlay();for(float Yaw:{0.f,90.f,180.f,270.f}){auto* Light=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,600),FRotator(-20,Yaw,0));Light->GetLightComponent()->SetMobility(EComponentMobility::Movable);Light->GetLightComponent()->SetIntensity(1.2f);Light->GetLightComponent()->SetCastShadows(false);}}
void AConstraintsHUD::DrawHUD(){Super::DrawHUD();if(auto* P=Cast<AConstraintsPlayer>(GetOwningPawn()))DrawText(FString::Printf(TEXT("Contacts | %s\nE pick up / Q release / Space jump / WASD move\nfeet: %s, %s | grip: %s"),*P->CaseName(),*P->IK->Result.FeetStatus[0],*P->IK->Result.FeetStatus[1],*P->IK->Result.GripStatus),FLinearColor::White,20,20,nullptr,1.4);}
