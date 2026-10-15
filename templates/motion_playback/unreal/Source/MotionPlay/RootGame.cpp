#include "RootGame.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
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
static const TArray<FString> Cases={TEXT("dash"),TEXT("roll"),TEXT("diagonal"),TEXT("wall"),TEXT("wall_diagonal"),TEXT("slow"),TEXT("fast"),TEXT("variable"),TEXT("pause"),TEXT("cancel"),TEXT("reentry"),TEXT("restart"),TEXT("controller_takeover"),TEXT("root_takeover")};
static TSharedPtr<FJsonValue> Num(double X){return MakeShared<FJsonValueNumber>(X);}
static TArray<TSharedPtr<FJsonValue>> Vec(FVector P){return {Num(P.X/100),Num(P.Y/100),Num(P.Z/100)};}
static AStaticMeshActor* Box(UWorld* World,FVector P,FVector Size,FLinearColor Color){
 auto* A=World->SpawnActor<AStaticMeshActor>(P,FRotator::ZeroRotator);auto* M=A->GetStaticMeshComponent();M->SetMobility(EComponentMobility::Movable);
 M->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));A->SetActorScale3D(Size/100);
 auto* Material=UMaterialInstanceDynamic::Create(LoadObject<UMaterial>(nullptr,TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")),A);Material->SetVectorParameterValue(TEXT("Color"),Color);M->SetMaterial(0,Material);M->SetCollisionProfileName(TEXT("BlockAll"));return A;
}
ARootPlayer::ARootPlayer(){
 PrimaryActorTick.bCanEverTick=true;Motion=CreateDefaultSubobject<UOAGDPlaybackComponent>(TEXT("Motion"));RootMotor=CreateDefaultSubobject<UOAGDRootMotionComponent>(TEXT("RootMotor"));
 GetMesh()->SetRelativeLocation(FVector(0,0,-90));GetMesh()->SetRelativeRotation(FRotator(0,-90,0));GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;GetMesh()->bEnableUpdateRateOptimizations=false;
 auto* M=GetCharacterMovement();M->bTickBeforeOwner=false;M->bOrientRotationToMovement=false;M->MaxWalkSpeed=100;M->MaxAcceleration=10000;M->BrakingDecelerationWalking=10000;
 CameraArm->bInheritYaw=false;CameraArm->bDoCollisionTest=false;CameraArm->TargetArmLength=500;CameraArm->TargetOffset=FVector(0,0,0);CameraArm->SetRelativeRotation(FRotator(-22,145,0));
}
void ARootPlayer::BeginPlay(){
 Super::BeginPlay();GetCharacterMovement()->AddTickPrerequisiteActor(this);FParse::Value(FCommandLine::Get(),TEXT("MotionReport="),Output);FParse::Value(FCommandLine::Get(),TEXT("MotionFrames="),FramesDirectory);FParse::Value(FCommandLine::Get(),TEXT("MotionView="),View);
 if(!FramesDirectory.IsEmpty())IFileManager::Get().MakeDirectory(*FramesDirectory,true);
 FString Content=TEXT("/Game/Playback");GConfig->GetString(TEXT("OAGDPlayback"),TEXT("RevisionRoot"),Content,GGameIni);
 GetMesh()->SetSkeletalMesh(LoadObject<USkeletalMesh>(nullptr,*(Content/TEXT("idle/idle.idle"))));
 Motion->Bindings=LoadObject<UOAGDPlaybackSet>(nullptr,*(Content/TEXT("Bindings.Bindings")));
 auto* BP=LoadClass<UAnimInstance>(nullptr,*(Content/TEXT("ABP_Player.ABP_Player_C")));GetMesh()->SetAnimInstanceClass(BP);
 if(!BP||!GetMesh()->GetSkeletalMeshAsset()||!RootMotor->Configure(Motion)){UE_LOG(LogTemp,Error,TEXT("Root mode rejected"));FGenericPlatformMisc::RequestExitWithStatus(false,3);return;}
 TArray<FString> Pairs;GConfig->GetArray(TEXT("OAGDPlayback"),TEXT("ObservedBones"),Pairs,GGameIni);
 for(const FString& Pair:Pairs){FString BoneRole,Bone;if(Pair.Split(TEXT("="),&BoneRole,&Bone))Bones.Add(FName(*BoneRole),FName(*Bone));}
 Motion->Marker.AddDynamic(this,&ARootPlayer::Marker);Motion->Ended.AddDynamic(this,&ARootPlayer::Ended);
 Wall=Box(GetWorld(),FVector(170,0,100),FVector(20,1200,200),FLinearColor(.75,.4,.12));
 Motion->Select(TEXT("idle"));NextCase();Observer=FWorldDelegates::OnWorldPostActorTick.AddUObject(this,&ARootPlayer::Observe);
}
void ARootPlayer::EndPlay(const EEndPlayReason::Type Reason){FWorldDelegates::OnWorldPostActorTick.Remove(Observer);Super::EndPlay(Reason);}
void ARootPlayer::SetupPlayerInputComponent(UInputComponent* Input){Super::SetupPlayerInputComponent(Input);Input->BindAxis(TEXT("Forward"),this,&ARootPlayer::Forward);Input->BindAxis(TEXT("Right"),this,&ARootPlayer::Right);Input->BindKey(EKeys::E,IE_Pressed,this,&ARootPlayer::Dash);Input->BindKey(EKeys::F,IE_Pressed,this,&ARootPlayer::Roll);Input->BindKey(EKeys::Q,IE_Pressed,this,&ARootPlayer::Cancel);}
void ARootPlayer::Forward(float V){Wish.X=V;}void ARootPlayer::Right(float V){Wish.Y=V;}void ARootPlayer::Dash(){Start();}void ARootPlayer::Roll(){Start(TEXT("roll"));}void ARootPlayer::Cancel(){RootMotor->Cancel();}
FString ARootPlayer::CaseName()const{return Cases.IsValidIndex(CaseIndex)?Cases[CaseIndex]:TEXT("interactive");}
void ARootPlayer::NextCase(){
 ++CaseIndex;Clock=0;Steps.Empty();RootMotor->Cancel();Motion->SetRate(1);ResetMotor(FVector(0,0,92));SetActorRotation(FRotator(0,CaseName().Contains(TEXT("diagonal"))?45:0,0));Previous=GetActorLocation();
 Wall->SetActorEnableCollision(CaseName().StartsWith(TEXT("wall")));Wall->SetActorHiddenInGame(!CaseName().StartsWith(TEXT("wall")));
}
void ARootPlayer::Start(FName Action,bool Restart){bool Ok=RootMotor->Start(Action,Restart);auto E=MakeShared<FJsonObject>();E->SetStringField(TEXT("case"),CaseName());E->SetNumberField(TEXT("t"),Clock);E->SetStringField(TEXT("kind"),TEXT("request"));E->SetStringField(TEXT("action"),Action.ToString());E->SetBoolField(TEXT("ok"),Ok);E->SetBoolField(TEXT("restart"),Restart);Events.Add(MakeShared<FJsonValueObject>(E));}
void ARootPlayer::Marker(FName Action,int32 Run,FName Name){auto E=MakeShared<FJsonObject>();E->SetStringField(TEXT("case"),CaseName());E->SetNumberField(TEXT("t"),Clock);E->SetStringField(TEXT("kind"),TEXT("marker"));E->SetStringField(TEXT("action"),Action.ToString());E->SetStringField(TEXT("name"),Name.ToString());E->SetNumberField(TEXT("run"),Run);Events.Add(MakeShared<FJsonValueObject>(E));}
void ARootPlayer::Ended(FName Action,int32 Run,FName Name){Marker(Action,Run,Name);Events.Last()->AsObject()->SetStringField(TEXT("kind"),TEXT("ended"));}
void ARootPlayer::Tick(float Delta){
 Super::Tick(Delta);if(!Motion->Bindings)return;Clock+=Delta;RootMotor->PrepareStep();const FString Name=CaseName();
 auto Once=[&](const FString& Key,float At,TFunction<void()> Call){if(Clock>=At&&!Steps.Contains(Key)){Steps.Add(Key);Call();}};
 if(!Output.IsEmpty()){
  Once(TEXT("start"),.2,[&]{Motion->SetRate(Name==TEXT("slow")?.5:Name==TEXT("fast")?2:1);Start(Name==TEXT("roll")?TEXT("roll"):TEXT("dash"));});
  if(Name==TEXT("variable")){Once(TEXT("rate"),.5,[&]{Motion->SetRate(.5);});Once(TEXT("rate2"),1.1,[&]{Motion->SetRate(2);});}
  if(Name==TEXT("pause")){Once(TEXT("pause"),.5,[&]{Motion->SetRate(0);});Once(TEXT("resume"),1.,[&]{Motion->SetRate(1);});}
  if(Name==TEXT("cancel")||Name==TEXT("reentry"))Once(TEXT("cancel"),.55,[&]{Cancel();});
  if(Name==TEXT("reentry"))Once(TEXT("again"),.85,[&]{Start();});
  if(Name==TEXT("restart"))Once(TEXT("restart"),.55,[&]{Start(TEXT("dash"),true);});
  if(Name.StartsWith(TEXT("wall")))Once(TEXT("wall_off"),1.6,[&]{Wall->SetActorEnableCollision(false);Wall->SetActorHiddenInGame(true);});
  Wish=FVector2D::ZeroVector;
  if(RootMotor->Active)Wish=FVector2D(3,0);
  else if(Name==TEXT("controller_takeover")&&Clock>=1.5&&Clock<2)Wish=FVector2D(1,0);
  else if(Name==TEXT("root_takeover")&&Clock<.2)Wish=FVector2D(1,0);
 }
 if(!RootMotor->Active){MoveWorld(Wish);Motion->Select(Wish.IsNearlyZero()?TEXT("idle"):TEXT("walk"));}
 if(View==TEXT("side")||View==TEXT("front")){CameraArm->TargetArmLength=400;CameraArm->SetRelativeRotation(FRotator(-5,View==TEXT("side")?-90:180,0));}
}
void ARootPlayer::Observe(UWorld* World,ELevelTick Type,float Delta){
 if(World!=GetWorld()||Output.IsEmpty()||!Motion->Bindings)return;
 auto F=MakeShared<FJsonObject>();F->SetStringField(TEXT("case"),CaseName());F->SetNumberField(TEXT("t"),Clock);F->SetNumberField(TEXT("dt"),Delta);F->SetArrayField(TEXT("actor"),Vec(GetActorLocation()-FVector(0,0,90)));F->SetArrayField(TEXT("actual"),Vec(GetActorLocation()-Previous));Previous=GetActorLocation();F->SetArrayField(TEXT("requested"),Vec(RootMotor->RequestedWorldCm));F->SetBoolField(TEXT("active"),RootMotor->Active);F->SetStringField(TEXT("state"),Motion->Current().ToString());F->SetNumberField(TEXT("clock"),Motion->PositionSeconds);F->SetNumberField(TEXT("rate"),Motion->Rate);F->SetNumberField(TEXT("generation"),Motion->Generation);F->SetNumberField(TEXT("extractions"),RootMotor->ExtractionCount);
 auto Poses=MakeShared<FJsonObject>();for(const auto& Pair:Bones)Poses->SetArrayField(Pair.Key.ToString(),Vec(GetMesh()->GetSocketLocation(Pair.Value)));F->SetObjectField(TEXT("bones"),Poses);Frames.Add(MakeShared<FJsonValueObject>(F));
 if(!FramesDirectory.IsEmpty()&&FrameIndex%12==0)FScreenshotRequest::RequestScreenshot(FramesDirectory/FString::Printf(TEXT("frame_%05d.png"),FrameIndex),false,false);++FrameIndex;
 if(Clock>=3){if(CaseIndex+1==Cases.Num()){
  auto Report=MakeShared<FJsonObject>();Report->SetStringField(TEXT("schema"),TEXT("oagd.root-runtime/1"));Report->SetStringField(TEXT("engine"),FEngineVersion::Current().ToString());Report->SetArrayField(TEXT("frames"),Frames);Report->SetArrayField(TEXT("events"),Events);FString Text;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*Output);FGenericPlatformMisc::RequestExit(false);
 }else NextCase();}
}
ARootGame::ARootGame(){DefaultPawnClass=ARootPlayer::StaticClass();HUDClass=ARootHUD::StaticClass();}
void ARootGame::BeginPlay(){Super::BeginPlay();Box(GetWorld(),FVector(0,0,-10),FVector(4000,4000,20),FLinearColor(.2,.28,.38));auto* Light=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,600),FRotator(-55,-25,0));Light->GetLightComponent()->SetIntensity(3);
 for(float Yaw:{0.f,90.f,180.f,270.f}){auto* Fill=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,600),FRotator(-20,Yaw,0));Fill->GetLightComponent()->SetIntensity(.8f);Fill->GetLightComponent()->SetCastShadows(false);}
 auto* Sky=GetWorld()->SpawnActor<ASkyLight>();Sky->GetLightComponent()->SetIntensity(1);}
void ARootHUD::DrawHUD(){Super::DrawHUD();if(auto* P=Cast<ARootPlayer>(GetOwningPawn()))DrawText(FString::Printf(TEXT("Root motion | %s\nE dash / F roll / Q cancel / WASD move\nowner: %s | clock %.2f | rate %.1f"),*P->CaseName(),P->RootMotor->Active?TEXT("animation"):TEXT("controller"),P->Motion->PositionSeconds,P->Motion->Rate),FLinearColor::White,20,20,nullptr,1.4);}
