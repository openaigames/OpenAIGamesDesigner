#include "MotionGame.h"
#include "Modules/ModuleManager.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/WorldSettings.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/CommandLine.h"
#include "Misc/App.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/EngineVersion.h"
#include "Misc/ConfigCacheIni.h"
#include "Serialization/JsonSerializer.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UnrealClient.h"
#include "HAL/FileManager.h"
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl,MotionPlay,"MotionPlay");
static TSharedPtr<FJsonValue> N(double V){return MakeShared<FJsonValueNumber>(V);}
static TArray<TSharedPtr<FJsonValue>> V(FVector P){return {N(P.X),N(P.Y),N(P.Z)};}

AMotionPlayer::AMotionPlayer(){
 PrimaryActorTick.bCanEverTick=true;
 Motion=CreateDefaultSubobject<UOAGDPlaybackComponent>(TEXT("Motion"));Session=CreateDefaultSubobject<UOAGDSessionComponent>(TEXT("Session"));
 LayerPlayer=CreateDefaultSubobject<UOAGDLayersComponent>(TEXT("LayerPlayer"));
 GetMesh()->SetRelativeLocation(FVector(0,0,-90));GetMesh()->SetRelativeRotation(FRotator(0,-90,0));
 GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
 GetMesh()->bEnableUpdateRateOptimizations=false;
 GetCharacterMovement()->MaxWalkSpeed=100;GetCharacterMovement()->JumpZVelocity=450;GetCharacterMovement()->GravityScale=1.63;
 GetCharacterMovement()->bOrientRotationToMovement=false;
 CameraArm->TargetArmLength=500;CameraArm->SetRelativeRotation(FRotator(-20,145,0));CameraArm->bInheritYaw=false;
}
void AMotionPlayer::BeginPlay(){
 Super::BeginPlay();Testing=FParse::Value(FCommandLine::Get(),TEXT("MotionReport="),Output);
 Replacement=FParse::Param(FCommandLine::Get(),TEXT("Replacement"));if(Replacement)ActionId=TEXT("action_v2");
 FParse::Value(FCommandLine::Get(),TEXT("MotionFrames="),FramesDirectory);
 FParse::Value(FCommandLine::Get(),TEXT("MotionView="),ReviewView);
 FParse::Value(FCommandLine::Get(),TEXT("MotionScenario="),Scenario);VariableFps=FParse::Param(FCommandLine::Get(),TEXT("MotionVariableFps"));
 if(Testing&&Scenario.Contains(TEXT("hitch")))GetWorld()->GetWorldSettings()->MaxUndilatedFrameTime=1.01f;
 if(!FramesDirectory.IsEmpty())IFileManager::Get().MakeDirectory(*FramesDirectory,true);
 FString ContentRoot=TEXT("/Game/Playback");GConfig->GetString(TEXT("OAGDPlayback"),TEXT("RevisionRoot"),ContentRoot,GGameIni);
 GetMesh()->SetSkeletalMesh(LoadObject<USkeletalMesh>(nullptr,*(ContentRoot/TEXT("idle/idle.idle"))));
 Motion->Bindings=LoadObject<UOAGDPlaybackSet>(nullptr,*(ContentRoot/TEXT("Bindings.Bindings")));
 UClass* BP=LoadClass<UAnimInstance>(nullptr,*(ContentRoot/TEXT("ABP_Player.ABP_Player_C")));
 if(!GetMesh()->GetSkeletalMeshAsset()||!Motion->Validate()||!BP){UE_LOG(LogTemp,Error,TEXT("Missing validated playback assets"));return;}
 if(Motion->Bindings->LayersEnabled){if(!LayerPlayer->Configure(Motion->Bindings)){FGenericPlatformMisc::RequestExitWithStatus(false,8);return;}LayerPlayer->Event.AddDynamic(this,&AMotionPlayer::OnLayerEvent);}
 GConfig->GetFloat(TEXT("OAGDPlayback"),TEXT("WalkSpeedMps"),WalkSpeedMps,GGameIni);
 GConfig->GetFloat(TEXT("OAGDPlayback"),TEXT("RunSpeedMps"),RunSpeedMps,GGameIni);
 TArray<FString> BonePairs;GConfig->GetArray(TEXT("OAGDPlayback"),TEXT("ObservedBones"),BonePairs,GGameIni);
 for(FName Name:{FName(TEXT("dst_root")),FName(TEXT("dst_foot_L")),FName(TEXT("dst_foot_R")),FName(TEXT("dst_hand_R")),FName(TEXT("dst_upperarm_R")),FName(TEXT("dst_forearm_R")),FName(TEXT("dst_spine")),FName(TEXT("dst_head")),FName(TEXT("dst_upperarm_L")),FName(TEXT("dst_forearm_L")),FName(TEXT("dst_hand_L"))})ObservedBones.Add(Name,Name);
 for(const FString& Pair:BonePairs){FString BindingRole,Bone;if(Pair.Split(TEXT("="),&BindingRole,&Bone))ObservedBones.Add(FName(*BindingRole),FName(*Bone));}
 for(const auto& Pair:ObservedBones)if(GetMesh()->GetBoneIndex(Pair.Value)==INDEX_NONE){UE_LOG(LogTemp,Error,TEXT("Missing observed bone: %s"),*Pair.Value.ToString());FGenericPlatformMisc::RequestExitWithStatus(false,7);return;}
 if(!Replacement)ActionId=Motion->Bindings->DefaultAction;Replacement=ActionId==TEXT("action_v2");
 GConfig->GetBool(TEXT("OAGDPlayback"),TEXT("LocomotionEnabled"),LocomotionEnabled,GGameIni);
 GConfig->GetBool(TEXT("OAGDPlayback"),TEXT("TurningEnabled"),TurningEnabled,GGameIni);
 GConfig->GetFloat(TEXT("OAGDPlayback"),TEXT("AccelerationMps2"),AccelerationMps2,GGameIni);
 GConfig->GetFloat(TEXT("OAGDPlayback"),TEXT("DecelerationMps2"),DecelerationMps2,GGameIni);
 GConfig->GetFloat(TEXT("OAGDPlayback"),TEXT("TurnSpeedDegS"),TurnSpeedDegS,GGameIni);
 if(LocomotionEnabled){
  GetCharacterMovement()->MaxAcceleration=AccelerationMps2*100;GetCharacterMovement()->BrakingDecelerationWalking=DecelerationMps2*100;
  GetCharacterMovement()->GroundFriction=0;GetCharacterMovement()->BrakingFriction=0;
  GetCharacterMovement()->AirControl=1;
  OnCharacterMovementUpdated.AddDynamic(this,&AMotionPlayer::MovementUpdated);
  GetMesh()->AddTickPrerequisiteComponent(GetCharacterMovement());
 }
 GetMesh()->SetAnimInstanceClass(BP);
 Motion->Marker.AddDynamic(this,&AMotionPlayer::OnMarker);Motion->Ended.AddDynamic(this,&AMotionPlayer::OnEnded);
 Session->Restarted.AddDynamic(this,&AMotionPlayer::ResetRules);Motion->Select(LocomotionEnabled?TEXT("locomotion"):TEXT("idle"));ResetMotor(FVector(0,0,92));
 // ACharacter already supplies movement/mesh tick prerequisites. Do not reverse them.
 ObservationHandle=FWorldDelegates::OnWorldPostActorTick.AddUObject(this,&AMotionPlayer::RecordFrame);
}
void AMotionPlayer::EndPlay(const EEndPlayReason::Type Reason){
 FWorldDelegates::OnWorldPostActorTick.Remove(ObservationHandle);Super::EndPlay(Reason);
}
void AMotionPlayer::SetupPlayerInputComponent(UInputComponent* Input){
 Super::SetupPlayerInputComponent(Input);
 Input->BindAxis(TEXT("Forward"),this,&AMotionPlayer::Forward);Input->BindAxis(TEXT("Right"),this,&AMotionPlayer::Right);
 Input->BindKey(EKeys::E,IE_Pressed,this,&AMotionPlayer::Trigger);Input->BindKey(EKeys::Q,IE_Pressed,this,&AMotionPlayer::Cancel);
 Input->BindKey(EKeys::F,IE_Pressed,this,&AMotionPlayer::FullTrigger);
 Input->BindKey(EKeys::R,IE_Pressed,this,&AMotionPlayer::Retry);Input->BindKey(EKeys::P,IE_Pressed,this,&AMotionPlayer::TogglePause);Input->BindKey(EKeys::SpaceBar,IE_Pressed,this,&AMotionPlayer::TryJump);
 Input->BindKey(EKeys::SpaceBar,IE_Released,this,&ACharacter::StopJumping);
 Input->BindKey(EKeys::LeftShift,IE_Pressed,this,&AMotionPlayer::RunPressed);Input->BindKey(EKeys::LeftShift,IE_Released,this,&AMotionPlayer::RunReleased);
}
void AMotionPlayer::Forward(float Value){Wish.X=Value;}
void AMotionPlayer::Right(float Value){Wish.Y=Value;}
void AMotionPlayer::RunPressed(){Fast=true;}void AMotionPlayer::RunReleased(){Fast=false;}
void AMotionPlayer::Trigger(){if(LayerPlayer->Bindings){if(!Paused)LayerRequest(TEXT("upper"),TEXT("upper_wave"));return;}if(!Paused&&TurnPhase==TEXT("none")&&!ActionLocked&&!GetCharacterMovement()->IsFalling()){ActionLocked=true;Motion->Select(ActionId);}}
void AMotionPlayer::FullTrigger(){if(LayerPlayer->Bindings&&!Paused)LayerRequest(TEXT("full"),TEXT("upper_alt"),5);}
void AMotionPlayer::Cancel(){if(LayerPlayer->Bindings){LayerPlayer->Cancel(TEXT("upper"));LayerPlayer->Cancel(TEXT("full"));return;}if(ActionLocked){Motion->Select(LocomotionEnabled?TEXT("locomotion"):TEXT("idle"));ActionLocked=false;}}
void AMotionPlayer::Retry(){Session->Restart();}
void AMotionPlayer::TryJump(){if(!Paused&&TurnPhase==TEXT("none")&&!ActionLocked)Jump();}
void AMotionPlayer::ResetRules(int32 Generation){if(Paused)TogglePause();if(LayerPlayer->Bindings)LayerPlayer->ResetLayers();CallbackCancel=false;TurnPhase=TEXT("none");TurnClock=0;TurnAngle=0;ActionLocked=false;Fast=false;Wish=FVector2D::ZeroVector;Motion->SetLocomotionSpeed(0);ResetMotor(FVector(0,0,92));SetActorRotation(FRotator::ZeroRotator);Motion->Reset(LocomotionEnabled?TEXT("locomotion"):TEXT("idle"));WasAir=false;LandUntil=0;StopJumping();}
void AMotionPlayer::OnMarker(FName Action,int32 Run,FName Name){
 if(Action==ActionId&&ActionLocked&&Name==TEXT("pulse"))++MarkerCount;
 auto E=MakeShared<FJsonObject>();E->SetNumberField(TEXT("t"),Time);E->SetStringField(TEXT("action"),Action.ToString().ToLower());E->SetNumberField(TEXT("run"),Run);E->SetStringField(TEXT("name"),Name.ToString().ToLower());E->SetStringField(TEXT("kind"),TEXT("marker"));E->SetNumberField(TEXT("position_s"),Motion->PositionSeconds);Events.Add(MakeShared<FJsonValueObject>(E));
}
void AMotionPlayer::OnEnded(FName Action,int32 Run,FName Reason){
 if(Action==ActionId){ActionLocked=false;if(Reason==TEXT("completed"))++Completed;}
 auto E=MakeShared<FJsonObject>();E->SetNumberField(TEXT("t"),Time);E->SetStringField(TEXT("action"),Action.ToString().ToLower());E->SetNumberField(TEXT("run"),Run);E->SetStringField(TEXT("name"),Reason.ToString().ToLower());E->SetStringField(TEXT("kind"),TEXT("ended"));E->SetNumberField(TEXT("position_s"),Motion->PositionSeconds);Events.Add(MakeShared<FJsonValueObject>(E));
}
void AMotionPlayer::ScriptedInput(){
 if(Scenario.StartsWith(TEXT("layers"))){LayerInput();return;}
 if(Scenario==TEXT("turning")){TurningInput();return;}
 if(Scenario==TEXT("locomotion")){LocomotionInput();return;}
 Forward(Time>=1&&Time<2.8?1:0);Right(Time>=2.8&&Time<4.2?1:0);Fast=Time>=2.8&&Time<4.2;
 auto Once=[&](const FString& Key,float At,TFunction<void()> Call){if(Time>=At&&!Steps.Contains(Key)){Steps.Add(Key);Call();}};
 Once(TEXT("jump"),4.4,[&]{TryJump();});Once(TEXT("jump_release"),4.45,[&]{StopJumping();});
 Once(TEXT("complete"),5.7,[&]{Trigger();});Once(TEXT("cancel_start"),7.3,[&]{Trigger();});Once(TEXT("cancel"),7.55,[&]{Cancel();});
 Once(TEXT("replay"),8.1,[&]{Trigger();});Once(TEXT("pause"),8.4,[&]{Motion->SetRate(0);});Once(TEXT("resume"),8.8,[&]{Motion->SetRate(2);});Once(TEXT("normal"),9.6,[&]{Motion->SetRate(1);});
 Once(TEXT("reset_active"),10,[&]{Trigger();});Once(TEXT("restart"),10.2,[&]{Retry();});Once(TEXT("after_reset"),10.7,[&]{Trigger();});
}
void AMotionPlayer::Tick(float Delta){
 Super::Tick(Delta);Time+=Delta;
 if(!Motion->Bindings)return;
 if(Testing)ScriptedInput();
 if(LayerPlayer->Bindings)ActionLocked=LayerPlayer->Full.Active||LayerPlayer->Full.Weight>1.e-6f;
 if(TurningEnabled&&!Paused)UpdateTurn(Delta);
 GetCharacterMovement()->MaxWalkSpeed=(LocomotionEnabled?RunSpeedMps:(Fast?RunSpeedMps:WalkSpeedMps))*100;
 if(!ActionLocked&&!Paused&&TurnPhase==TEXT("none")){MoveWorld(LocomotionEnabled?Wish*(Fast?1.f:WalkSpeedMps/RunSpeedMps):Wish);if(!LocomotionEnabled&&!Wish.IsNearlyZero()){auto R=Wish.GetSafeNormal();SetActorRotation(FMath::RInterpTo(GetActorRotation(),FVector(R.X,R.Y,0).Rotation(),Delta,12));}}
 if(!ActionLocked&&!Paused&&TurnPhase!=TEXT("pivot")){
  if(GetCharacterMovement()->IsFalling()){Motion->Select(GetVelocity().Z>0?TEXT("jump"):TEXT("fall"));WasAir=true;}
  else{if(WasAir){LandUntil=Time+.3f;WasAir=false;}
   Motion->Select(Time<LandUntil?TEXT("land"):LocomotionEnabled?TEXT("locomotion"):!Wish.IsNearlyZero()?(Fast?TEXT("run"):TEXT("walk")):TEXT("idle"));}
 }
 if(LastState!=Motion->Current()){auto T=MakeShared<FJsonObject>();T->SetNumberField(TEXT("t"),Time);T->SetStringField(TEXT("from"),LastState.ToString().ToLower());T->SetStringField(TEXT("to"),Motion->Current().ToString().ToLower());Transitions.Add(MakeShared<FJsonValueObject>(T));LastState=Motion->Current();TransitionAt=Time;}
 if(ReviewView==TEXT("side")||ReviewView==TEXT("front")){
  CameraArm->TargetArmLength=340;CameraArm->TargetOffset=FVector(0,0,15);CameraArm->SetRelativeRotation(FRotator(-3,GetActorRotation().Yaw+(ReviewView==TEXT("side")?-90:180),0));
 }
}
void AMotionPlayer::RecordFrame(UWorld* World,ELevelTick TickType,float Delta){
 // A pose can already have evaluated on the frame that pause is requested.
 // Always consume that real pose time; subsequent paused samples are constant.
 // Freezing yaw early would twist planted feet against the last evaluated pose.
 if(World==GetWorld()&&Motion->Bindings&&TurnPhase==TEXT("pivot")){
  auto Rot=GetActorRotation();Rot.Yaw=TurnStartYaw+TurnAngle*TurnFraction(Motion->PositionSeconds);SetActorRotation(Rot);
 }
 if(World==GetWorld()&&Testing&&Motion->Bindings){
  // Observe after movement and native mesh evaluation have both completed.
  // Reading in the actor's input tick mixed an old pose with current movement.
  auto F=MakeShared<FJsonObject>();F->SetNumberField(TEXT("t"),Time);F->SetNumberField(TEXT("dt"),Delta);F->SetBoolField(TEXT("paused"),Paused);
 F->SetStringField(TEXT("turn_phase"),TurnPhase);F->SetNumberField(TEXT("turn_angle_deg"),TurnAngle);F->SetArrayField(TEXT("wish"),{N(Wish.X),N(Wish.Y)});
 F->SetNumberField(TEXT("speed_mps"),GetVelocity().Size2D()/100);F->SetNumberField(TEXT("move_weight"),Motion->MoveWeight);F->SetNumberField(TEXT("run_weight"),Motion->RunWeight);F->SetNumberField(TEXT("cycle_hz"),Motion->CycleHz);F->SetNumberField(TEXT("transition_age_s"),Time-TransitionAt);
 auto Times=MakeShared<FJsonObject>();Times->SetNumberField(TEXT("walk"),Motion->WalkTime);Times->SetNumberField(TEXT("run"),Motion->RunTime);F->SetObjectField(TEXT("clip_times"),Times);F->SetStringField(TEXT("state"),Motion->Current().ToString().ToLower());F->SetNumberField(TEXT("position_s"),Motion->PositionSeconds);F->SetNumberField(TEXT("rate"),Motion->Rate);
  F->SetArrayField(TEXT("actor"),V(GetActorLocation()/100));F->SetBoolField(TEXT("floor"),!GetCharacterMovement()->IsFalling());auto Bones=MakeShared<FJsonObject>();
  F->SetArrayField(TEXT("forward"),V(GetActorForwardVector()));
  for(const auto& Pair:ObservedBones){
   auto P=GetMesh()->GetSocketTransform(Pair.Value);auto B=MakeShared<FJsonObject>();B->SetArrayField(TEXT("p"),V(P.GetLocation()/100));auto Q=P.GetRotation();B->SetArrayField(TEXT("q"),{N(Q.X),N(Q.Y),N(Q.Z),N(Q.W)});Bones->SetObjectField(Pair.Key.ToString().ToLower(),B);
  }
  F->SetObjectField(TEXT("bones"),Bones);Frames.Add(MakeShared<FJsonValueObject>(F));
  if(LayerPlayer->Bindings){
   auto States=MakeShared<FJsonObject>();
   for(FName Name:{FName(TEXT("upper")),FName(TEXT("full"))}){const auto* S=LayerPlayer->State(Name);auto Row=MakeShared<FJsonObject>();
    Row->SetStringField(TEXT("action"),S->Action.IsNone()?TEXT(""):S->Action.ToString().ToLower());Row->SetNumberField(TEXT("run"),S->Run);Row->SetBoolField(TEXT("active"),S->Active);Row->SetNumberField(TEXT("bank"),S->Bank);Row->SetNumberField(TEXT("mix"),S->Mix);Row->SetNumberField(TEXT("weight"),S->Weight);Row->SetNumberField(TEXT("target"),S->Target);Row->SetNumberField(TEXT("rate"),S->Rate);Row->SetNumberField(TEXT("priority"),S->Priority);Row->SetNumberField(TEXT("position_s"),S->PositionSeconds);Row->SetNumberField(TEXT("total_s"),S->TotalSeconds);States->SetObjectField(Name.ToString(),Row);
   }F->SetObjectField(TEXT("layers"),States);
  }
  if(!FramesDirectory.IsEmpty()&&FrameIndex%4==0)FScreenshotRequest::RequestScreenshot(FramesDirectory/FString::Printf(TEXT("frame_%05d.png"),FrameIndex/4),false,false);
  ++FrameIndex;
  if(VariableFps)FApp::SetFixedDeltaTime((int32(Time*2)%2)==0?1./30:1./60);
  if(Scenario.Contains(TEXT("hitch"))){if(!HitchUsed)LayerNormalDelta=Delta;if(Time>=17&&!HitchUsed){HitchUsed=true;FApp::SetFixedDeltaTime(1.);}else if(HitchUsed)FApp::SetFixedDeltaTime(LayerNormalDelta);}
 if(Time>=((Scenario==TEXT("turning")||Scenario.StartsWith(TEXT("layers")))?40.f:Scenario==TEXT("locomotion")?22.f:12.4f)){Testing=false;Finish();}
 }
}
void AMotionPlayer::Finish(){
 auto D=MakeShared<FJsonObject>();D->SetStringField(TEXT("engine"),TEXT("unreal"));D->SetStringField(TEXT("scenario"),Scenario);D->SetBoolField(TEXT("variable_fps"),VariableFps);D->SetStringField(TEXT("engine_version"),FEngineVersion::Current().ToString());D->SetStringField(TEXT("revision"),Motion->Bindings->Revision);D->SetStringField(TEXT("action_id"),ActionId.ToString().ToLower());D->SetStringField(TEXT("view"),ReviewView);D->SetStringField(TEXT("method"),TEXT("AnimBlueprint sequence players and native CharacterMovement; no seek"));D->SetStringField(TEXT("input"),TEXT("same project input handlers; scripted schedule, not human play"));
 D->SetArrayField(TEXT("frames"),Frames);D->SetArrayField(TEXT("events"),Events);D->SetArrayField(TEXT("transitions"),Transitions);D->SetNumberField(TEXT("marker_count"),MarkerCount);D->SetNumberField(TEXT("completed_runs"),Completed);D->SetNumberField(TEXT("generation"),Session->Generation);
 if(LayerPlayer->Bindings){D->SetArrayField(TEXT("layer_events"),LayerEvents);D->SetArrayField(TEXT("layer_requests"),LayerRequests);D->SetNumberField(TEXT("layer_faults"),LayerPlayer->ClockFaults);D->SetStringField(TEXT("method"),TEXT("native base graph, LayeredBoneBlend upper mask and full TwoWayBlend; bank initialized only on request"));}
 auto O=MakeShared<FJsonObject>();for(const auto& Pair:ObservedBones)O->SetStringField(Pair.Key.ToString(),Pair.Value.ToString());D->SetObjectField(TEXT("observation_bones"),O);
 auto S=MakeShared<FJsonObject>();S->SetNumberField(TEXT("walk"),WalkSpeedMps);S->SetNumberField(TEXT("run"),RunSpeedMps);D->SetObjectField(TEXT("movement_speeds_mps"),S);
 FString Text;FJsonSerializer::Serialize(D,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*Output);UKismetSystemLibrary::QuitGame(this,UGameplayStatics::GetPlayerController(this,0),EQuitPreference::Quit,false);
}
AMotionGame::AMotionGame(){DefaultPawnClass=AMotionPlayer::StaticClass();HUDClass=AMotionHUD::StaticClass();}
void AMotionGame::BeginPlay(){
 Super::BeginPlay();
 auto* A=GetWorld()->SpawnActor<AStaticMeshActor>(FVector(0,0,-10),FRotator::ZeroRotator);auto* M=A->GetStaticMeshComponent();M->SetMobility(EComponentMobility::Movable);M->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));M->SetWorldScale3D(FVector(80,80,.2));M->SetCollisionProfileName(TEXT("BlockAll"));
 auto* L=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,600),FRotator(-55,-25,0));L->GetLightComponent()->SetIntensity(3);
 // The black empty environment has no ambient capture. Soft fills keep face,
 // chest and toes readable from both review cameras without changing the skin.
 for(float Yaw:{45.f,135.f,225.f,315.f}){
  auto* Fill=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,600),FRotator(-20,Yaw,0));Fill->GetLightComponent()->SetIntensity(.6f);Fill->GetLightComponent()->SetCastShadows(false);
 }
 auto* Sky=GetWorld()->SpawnActor<ASkyLight>();Sky->GetLightComponent()->SetIntensity(1);
}
void AMotionHUD::DrawHUD(){Super::DrawHUD();auto* P=Cast<AMotionPlayer>(UGameplayStatics::GetPlayerPawn(this,0));if(!P)return;
 DrawText(FString::Printf(TEXT("OAGD / UE 5.8 / PLAYABLE MOTION\nWASD move   Shift run   Space jump   E upper   F full   Q cancel   R reset   P pause\nState: %s   Clip: %.2fs   Events: %d   Revision: %s\nFront = character face / toes"),*P->Motion->Current().ToString().ToLower(),P->Motion->PositionSeconds,P->MarkerCount,P->Motion->Bindings?*P->Motion->Bindings->Revision:TEXT("missing")),FColor::White,22,20,nullptr,1.35f);
}

void AMotionPlayer::MovementUpdated(float Delta,FVector OldLocation,FVector OldVelocity){
 if(Paused)return;
 Motion->SetLocomotionSpeed(GetVelocity().Size2D()/100);
 FVector Horizontal=GetVelocity();Horizontal.Z=0;
 if(TurnPhase==TEXT("none")&&Horizontal.Size()>2){auto Rot=GetActorRotation();Rot.Yaw=FMath::FixedTurn(Rot.Yaw,Horizontal.Rotation().Yaw,TurnSpeedDegS*Delta);SetActorRotation(Rot);}
}
void AMotionPlayer::TogglePause(){
 Paused=!Paused;
 if(Paused){PauseVelocity=GetVelocity();PauseMovementMode=GetCharacterMovement()->MovementMode;GetCharacterMovement()->DisableMovement();}
 else{GetCharacterMovement()->SetMovementMode(EMovementMode(PauseMovementMode));GetCharacterMovement()->Velocity=PauseVelocity;}
 GetMesh()->GlobalAnimRateScale=Paused?0:1;
}
void AMotionPlayer::LocomotionInput(){
 Wish=FVector2D::ZeroVector;Fast=false;
 if(Time>=1&&Time<5.5){Wish={1,0};Fast=Time>=3;}
 else if(Time>=5.5&&Time<6.4){Wish={.65,0};Fast=true;}
 else if(Time>=7.4&&Time<8.4)Wish={1,0};
 else if(Time>=8.4&&Time<9.2)Wish={-1,0};
 else if(Time>=9.2&&Time<9.5)Wish={0,1};
 else if(Time>=9.5&&Time<9.8)Wish={0,-1};
 else if(Time>=9.8&&Time<10.4)Wish={1,0};
 else if(Time>=11.4&&Time<13.3){Wish=FVector2D(1,1).GetSafeNormal();Fast=true;}
 else if(Time>=13.3&&Time<15)Wish={1,0};
 else if(Time>=18&&Time<19){Wish={1,0};Fast=(int32(Time*10)%2)==0;}
 auto Once=[&](FString Key,float At,TFunction<void()> F){if(Time>=At&&!Steps.Contains(Key)){Steps.Add(Key);F();}};
 Once(TEXT("jump"),11.6,[&]{TryJump();});Once(TEXT("jump_release"),11.65,[&]{StopJumping();});
 Once(TEXT("pause"),14,[&]{TogglePause();});Once(TEXT("resume"),14.5,[&]{TogglePause();});
 Once(TEXT("complete"),16,[&]{Trigger();});Once(TEXT("cancel_start"),17.4,[&]{Trigger();});Once(TEXT("cancel"),17.65,[&]{Cancel();});
 Once(TEXT("restart"),19.3,[&]{Retry();});Once(TEXT("after_reset"),20,[&]{Trigger();});
}

float AMotionPlayer::TurnFraction(float Position)const{
 const float Count=FMath::Abs(TurnAngle)/45.f,U=(Position-.2f)/.6f;
 if(U<=0)return 0;if(U>=Count)return 1;
 const float Step=FMath::FloorToFloat(U),X=FMath::Clamp((U-Step-.1f)/.8f,0.f,1.f);
 return (Step+X*X*(3-2*X))/Count;
}
void AMotionPlayer::UpdateTurn(float Delta){
 if(TurnPhase==TEXT("pivot")){
  const float U=(Motion->PositionSeconds-.2f)/.6f;
  const bool AtStep=U>.92f&&FMath::Abs(U-FMath::RoundToFloat(U))<.075f;
  const bool Changed=Wish.Size()<=.1||FMath::Abs(FMath::FindDeltaAngleDegrees(TurnStartYaw+TurnAngle,FVector(Wish.X,Wish.Y,0).Rotation().Yaw))>30;
  if(Motion->Finished||(AtStep&&Changed)){TurnPhase=TEXT("recover");TurnClock=0;Motion->Select(TEXT("locomotion"));}return;
 }
 if(TurnPhase==TEXT("recover")){TurnClock+=Delta;if(TurnClock>=.2f)TurnPhase=TEXT("none");return;}
 if(ActionLocked||GetCharacterMovement()->IsFalling()){TurnPhase=TEXT("none");return;}
 const float Error=Wish.Size()>.1?FMath::FindDeltaAngleDegrees(GetActorRotation().Yaw,FVector(Wish.X,Wish.Y,0).Rotation().Yaw):0;
 if(FMath::Abs(Error)<30){TurnPhase=TEXT("none");TurnClock=0;return;}
 if(TurnPhase==TEXT("none")){TurnPhase=TEXT("brake");TurnClock=0;}
 if(GetVelocity().Size2D()>.5){TurnClock=0;return;}
 TurnPhase=TEXT("settle");TurnClock+=Delta;if(TurnClock<.2f)return;
 const int32 Magnitude=FMath::Abs(Error)>=135?180:FMath::Abs(Error)>=67.5?90:45;
 TurnAngle=Magnitude*(Error>0?1:-1);TurnStartYaw=GetActorRotation().Yaw;
 TurnClip=FName(*FString::Printf(TEXT("turn_%s_%d"),TurnAngle>0?TEXT("r"):TEXT("l"),Magnitude));
 TurnPhase=TEXT("pivot");Motion->Select(TurnClip);
}
void AMotionPlayer::TurningInput(){
 Wish=FVector2D::ZeroVector;Fast=false;
 if(Time>=1&&Time<3)Wish={1,0};
 else if(Time>=3&&Time<7)Wish={0,1};
 else if(Time>=7&&Time<11){Wish={1,0};Fast=true;}
 else if(Time>=11&&Time<16){Wish={-1,0};Fast=true;}
 else if(Time>=16&&Time<21)Wish={1,0};
 else if(Time>=21&&Time<24)Wish=FVector2D(1,1).GetSafeNormal();
 else if(Time>=24&&Time<28)Wish={1,0};
 else if(Time>=28&&Time<28.4)Wish={-1,0};
 else if(Time>=28.4&&Time<28.7)Wish={0,1};
 else if(Time>=28.7&&Time<29)Wish={0,-1};
 else if(Time>=29&&Time<34)Wish={1,0};
 auto Once=[&](FString Key,float At,TFunction<void()> F){if(Time>=At&&!Steps.Contains(Key)){Steps.Add(Key);F();}};
 Once(TEXT("pause"),12,[&]{TogglePause();});Once(TEXT("resume"),12.5,[&]{TogglePause();});
 Once(TEXT("gesture"),35,[&]{Trigger();});Once(TEXT("restart"),37,[&]{Retry();});Once(TEXT("after_reset"),38,[&]{Trigger();});
}

void AMotionPlayer::OnLayerEvent(const FOAGDLayerEvent& E){
 auto R=MakeShared<FJsonObject>();R->SetNumberField(TEXT("t"),Time);R->SetStringField(TEXT("channel"),E.Channel.ToString().ToLower());R->SetStringField(TEXT("action"),E.Action.ToString().ToLower());R->SetNumberField(TEXT("run"),E.Run);R->SetStringField(TEXT("kind"),E.Kind.ToString().ToLower());R->SetStringField(TEXT("name"),E.Name.ToString().ToLower());R->SetNumberField(TEXT("cycle"),E.Cycle);R->SetNumberField(TEXT("at_s"),E.AtSeconds);R->SetNumberField(TEXT("position_s"),E.PositionSeconds);R->SetNumberField(TEXT("total_s"),E.TotalSeconds);R->SetNumberField(TEXT("weight"),E.Weight);LayerEvents.Add(MakeShared<FJsonValueObject>(R));
 if(CallbackCancel&&E.Channel==TEXT("upper")&&E.Kind==TEXT("marker")&&E.Name==TEXT("pulse")){CallbackCancel=false;LayerPlayer->Cancel(TEXT("upper"),TEXT("callback_cancelled"));}
}
void AMotionPlayer::LayerRequest(FName Channel,FName Action,int32 Priority,float Weight,float Speed,bool Restart){
 if(Scenario.EndsWith(TEXT("baseline")))return;
 const bool Allowed=Channel!=TEXT("full")||(TurnPhase==TEXT("none")&&!GetCharacterMovement()->IsFalling()&&GetVelocity().Size2D()<2);
 const bool Accepted=Allowed&&LayerPlayer->Play(Channel,Action,Priority,Weight,Speed,Restart);
 auto R=MakeShared<FJsonObject>();R->SetNumberField(TEXT("t"),Time);R->SetStringField(TEXT("op"),TEXT("play"));R->SetStringField(TEXT("channel"),Channel.ToString());R->SetStringField(TEXT("action"),Action.ToString());R->SetNumberField(TEXT("priority"),Priority);R->SetNumberField(TEXT("weight"),Weight);R->SetNumberField(TEXT("rate"),Speed);R->SetBoolField(TEXT("restart"),Restart);R->SetBoolField(TEXT("accepted"),Accepted);R->SetStringField(TEXT("reason"),Allowed?(LayerPlayer->Rejection.IsNone()?TEXT(""):LayerPlayer->Rejection.ToString()):TEXT("project_motion"));R->SetNumberField(TEXT("run"),LayerPlayer->State(Channel)->Run);LayerRequests.Add(MakeShared<FJsonValueObject>(R));
}
void AMotionPlayer::LayerChange(FName Op,FName Channel,float Value){
 if(Scenario.EndsWith(TEXT("baseline")))return;bool Accepted=false;
 if(Op==TEXT("rate"))Accepted=LayerPlayer->SetLayerRate(Channel,Value);else if(Op==TEXT("weight"))Accepted=LayerPlayer->SetLayerWeight(Channel,Value);else if(Op==TEXT("cancel"))Accepted=LayerPlayer->Cancel(Channel);
 auto R=MakeShared<FJsonObject>();R->SetNumberField(TEXT("t"),Time);R->SetStringField(TEXT("op"),Op.ToString());R->SetStringField(TEXT("channel"),Channel.ToString());R->SetNumberField(TEXT("value"),Value);R->SetBoolField(TEXT("accepted"),Accepted);R->SetNumberField(TEXT("run"),LayerPlayer->State(Channel)->Run);LayerRequests.Add(MakeShared<FJsonValueObject>(R));
}

// Layer scripted cases: generated from the recorded layer-case.json.
void AMotionPlayer::LayerInput(){
 Wish=FVector2D::ZeroVector;Fast=false;
 if((Time>=1&&Time<10)||(Time>=15&&Time<21)){Wish={1,0};Fast=Time>=4&&Time<7;}else if(Time>=21&&Time<25)Wish={0,1};
 auto Once=[&](FString Key,float At,TFunction<void()> F){if(Time>=At&&!Steps.Contains(Key)){Steps.Add(Key);F();}};
 Once(TEXT("layer_0"),1.6f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),1,1,1,true);});
 Once(TEXT("layer_1"),3.2f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_loop"),1,0.35f,1,true);});
 Once(TEXT("layer_2"),4.0f,[&]{LayerChange(TEXT("weight"),TEXT("upper"),1);});
 Once(TEXT("layer_3"),4.7f,[&]{LayerChange(TEXT("rate"),TEXT("upper"),2);});
 Once(TEXT("layer_4"),5.6f,[&]{if(Paused!=true)TogglePause();});
 Once(TEXT("layer_5"),6.1f,[&]{if(Paused!=false)TogglePause();});
 Once(TEXT("layer_6"),6.4f,[&]{LayerChange(TEXT("rate"),TEXT("upper"),0);});
 Once(TEXT("layer_7"),6.9f,[&]{LayerChange(TEXT("rate"),TEXT("upper"),0.5f);});
 Once(TEXT("layer_8"),7.5f,[&]{LayerChange(TEXT("rate"),TEXT("upper"),4);});
 Once(TEXT("layer_9"),8.3f,[&]{LayerChange(TEXT("cancel"),TEXT("upper"),0);});
 Once(TEXT("layer_10"),8.55f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),1,1,4,true);});
 Once(TEXT("layer_11"),9.0f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_alt"),1,1,4,true);});
 Once(TEXT("layer_12"),9.1f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_alt"),1,1,4,false);});
 Once(TEXT("layer_13"),9.4f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),3,1,1,true);});
 Once(TEXT("layer_14"),9.43f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_alt"),5,1,1,true);});
 Once(TEXT("layer_15"),9.6f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_alt"),1,1,1,true);});
 Once(TEXT("layer_16"),9.8f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_alt"),4,1,1,true);});
 Once(TEXT("layer_17"),10.8f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_loop"),4,1,1,true);});
 Once(TEXT("layer_18"),11.4f,[&]{LayerRequest(TEXT("full"),TEXT("upper_alt"),5,1,1,true);});
 Once(TEXT("layer_19"),11.7f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),20,1,1,true);});
 Once(TEXT("layer_20"),13.0f,[&]{LayerRequest(TEXT("full"),TEXT("upper_wave"),5,1,0.5f,true);});
 Once(TEXT("layer_21"),13.4f,[&]{LayerChange(TEXT("cancel"),TEXT("full"),0);});
 Once(TEXT("layer_22"),13.45f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),20,1,1,true);});
 Once(TEXT("layer_23"),13.7f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),1,1,1,true);});
 Once(TEXT("layer_24"),14.0f,[&]{Retry();});
 Once(TEXT("layer_25"),14.3f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),1,1,1,true);});
 Once(TEXT("layer_26"),15.2f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_loop"),1,1,1,true);});
 Once(TEXT("layer_27"),16.0f,[&]{LayerChange(TEXT("weight"),TEXT("upper"),0);});
 Once(TEXT("layer_28"),16.5f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_loop"),1,1,4,true);});
 Once(TEXT("layer_29"),18.5f,[&]{LayerChange(TEXT("cancel"),TEXT("upper"),0);});
 Once(TEXT("layer_30"),19.0f,[&]{CallbackCancel=true;});
 Once(TEXT("layer_31"),19.0f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),1,1,1,true);});
 Once(TEXT("layer_32"),21.4f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),1,1,1,true);});
 Once(TEXT("layer_33"),22.0f,[&]{LayerRequest(TEXT("full"),TEXT("upper_alt"),5,1,1,true);});
 Once(TEXT("layer_34"),25.5f,[&]{TryJump();});
 Once(TEXT("layer_35"),25.55f,[&]{StopJumping();});
 Once(TEXT("layer_36"),25.7f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),1,1,1,true);});
 Once(TEXT("layer_37"),25.8f,[&]{LayerRequest(TEXT("full"),TEXT("upper_alt"),5,1,1,true);});
 Once(TEXT("layer_38"),27.8f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_loop"),1,1,1,true);});
 Once(TEXT("layer_39"),28.0f,[&]{Retry();});
 Once(TEXT("layer_40"),29.0f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),1,0.5f,1,true);});
 Once(TEXT("layer_41"),30.0f,[&]{LayerChange(TEXT("weight"),TEXT("upper"),1);});
 Once(TEXT("layer_42"),30.4f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_alt"),1,1,4,true);});
 Once(TEXT("layer_43"),31.2f,[&]{LayerRequest(TEXT("full"),TEXT("upper_wave"),1,1,1,true);});
 Once(TEXT("layer_44"),31.45f,[&]{LayerRequest(TEXT("full"),TEXT("upper_alt"),2,1,1,true);});
 Once(TEXT("layer_45"),31.5f,[&]{LayerRequest(TEXT("full"),TEXT("upper_wave"),1,1,1,true);});
 Once(TEXT("layer_46"),32.7f,[&]{LayerChange(TEXT("cancel"),TEXT("full"),0);});
 Once(TEXT("layer_47"),33.0f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_loop"),1,0.35f,2,true);});
 Once(TEXT("layer_48"),34.0f,[&]{Retry();});
 Once(TEXT("layer_49"),35.0f,[&]{LayerRequest(TEXT("upper"),TEXT("upper_wave"),1,1,1,true);});
 Once(TEXT("layer_50"),36.8f,[&]{LayerRequest(TEXT("full"),TEXT("full_tuck"),2,1,0.5f,true);});
}
