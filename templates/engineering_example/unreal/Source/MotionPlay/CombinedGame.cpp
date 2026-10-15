#include "CombinedGame.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Camera/CameraComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/LevelStreamingDynamic.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundBase.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/EngineVersion.h"
#include "Serialization/JsonSerializer.h"
#include "HAL/FileManager.h"
#include "UnrealClient.h"
#include "NavigationSystem.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "ProceduralMeshComponent.h"
#if WITH_EDITOR
#include "Builders/CubeBuilder.h"
#include "ActorFactories/ActorFactory.h"
#endif
static TSharedPtr<FJsonValue> Num(double X){return MakeShared<FJsonValueNumber>(X);}
static TSharedPtr<FJsonValue> Str(const FString& X){return MakeShared<FJsonValueString>(X);}
static TSharedPtr<FJsonObject> ReadJson(const FString& Path){FString Text;TSharedPtr<FJsonObject> O;FFileHelper::LoadFileToString(Text,*Path);FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),O);return O;}
static FString Data(const FString& Name){return FPaths::ProjectContentDir()/TEXT("OAGDData")/Name;}
static FVector V(const TArray<TSharedPtr<FJsonValue>>& A){return FVector(-A[2]->AsNumber(),A[0]->AsNumber(),A[1]->AsNumber())*100;}
static TArray<TSharedPtr<FJsonValue>> Source(FVector P){return {Num(P.Y/100),Num(P.Z/100),Num(-P.X/100)};}
static AStaticMeshActor* Box(UWorld* W,FVector Position,FVector Size,FLinearColor Color){
 auto* A=W->SpawnActor<AStaticMeshActor>(Position,FRotator::ZeroRotator);auto* M=A->GetStaticMeshComponent();M->SetMobility(EComponentMobility::Movable);M->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));A->SetActorScale3D(Size/100);M->SetCollisionProfileName(TEXT("NoCollision"));M->SetCanEverAffectNavigation(false);
 auto* Mat=UMaterialInstanceDynamic::Create(LoadObject<UMaterial>(nullptr,TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")),A);Mat->SetVectorParameterValue(TEXT("Color"),Color);M->SetMaterial(0,Mat);return A;
}
bool UCombinedMapTools::BuildBounds(UObject* Context){
#if WITH_EDITOR
 UWorld* W=Cast<UWorld>(Context);if(!W&&Context)W=Context->GetWorld();if(!W)return false;
 auto* Bounds=W->SpawnActor<ANavMeshBoundsVolume>(FVector(250,0,150),FRotator::ZeroRotator);auto* Builder=NewObject<UCubeBuilder>();Builder->X=1800;Builder->Y=3000;Builder->Z=600;UActorFactory::CreateBrushForVolumeActor(Bounds,Builder);
 if(auto* N=FNavigationSystem::GetCurrent<UNavigationSystemV1>(W)){N->OnNavigationBoundsUpdated(Bounds);N->Build();}return true;
#else
 return false;
#endif
}
bool UCombinedMapTools::BuildGeneratedScene(UObject* Context){
#if WITH_EDITOR
 UWorld* W=Cast<UWorld>(Context);if(!W&&Context)W=Context->GetWorld();if(!W)return false;
 for(TActorIterator<AOAGDGeometry> It(W);It;++It)return false;
 TArray<AOAGDGeometry*> Objects;FString Error;if(!AOAGDGeometry::LoadScene(W,FPaths::ProjectContentDir()/TEXT("generated/scene/scene.json"),Objects,Error))return false;
 auto* Mat=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Scene/Vertex.Vertex"));for(auto* A:Objects){A->Geometry->SetMobility(EComponentMobility::Static);A->Geometry->SetCanEverAffectNavigation(true);if(Mat)A->Geometry->SetMaterial(0,Mat);}return true;
#else
 return false;
#endif
}
FOAGDInteractionOffer UCombinedTarget::Query_Implementation(AActor* R){FOAGDInteractionOffer O;auto* P=Cast<ACombinedPlayer>(R);O.Allowed=P&&!P->Held;O.Reason=O.Allowed?TEXT(""):TEXT("already held");return O;}
bool UCombinedTarget::Execute_Implementation(AActor* R){auto* P=Cast<ACombinedPlayer>(R);return P&&P->Take();}
ACombinedPulse::ACombinedPulse(){RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));Shape=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pulse"));Shape->SetupAttachment(RootComponent);Shape->SetMobility(EComponentMobility::Movable);Shape->SetCollisionProfileName(TEXT("NoCollision"));Shape->SetCanEverAffectNavigation(false);}
void ACombinedPulse::Sample_Implementation(float Age,float Strength,FLinearColor Color){if(!Shape->GetStaticMesh())Shape->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));if(!Tint){auto* Material=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Feedback/FeedbackTint.FeedbackTint"));if(Material){Tint=UMaterialInstanceDynamic::Create(Material,this);Shape->SetMaterial(0,Tint);}}if(Tint)Tint->SetVectorParameterValue(TEXT("Tint"),Color);float Scale=(1+FMath::Fmod(Age,1.f))*FMath::Max(.1f,Strength);Shape->SetRelativeScale3D(FVector(Scale,Scale,.04));Shape->SetRelativeLocation(FVector(0,0,12));}
ACombinedNpc::ACombinedNpc(){PrimaryActorTick.bCanEverTick=true;GetCharacterMovement()->bTickBeforeOwner=false;GetCharacterMovement()->bRunPhysicsWithNoController=true;GetCharacterMovement()->MaxWalkSpeed=70;GetCapsuleComponent()->SetCanEverAffectNavigation(false);GetMesh()->SetCanEverAffectNavigation(false);}
ACombinedPlayer::ACombinedPlayer(){
 PrimaryActorTick.bCanEverTick=true;Router=CreateDefaultSubobject<UOAGDInputComponent>(TEXT("InputRouter"));Scenes=CreateDefaultSubobject<UOAGDSceneComponent>(TEXT("Scenes"));Feedback=CreateDefaultSubobject<UOAGDFeedbackComponent>(TEXT("Feedback"));Interaction=CreateDefaultSubobject<UOAGDInteractionComponent>(TEXT("Interaction"));Nav=CreateDefaultSubobject<UOAGDNavigationComponent>(TEXT("Navigation"));Motion=CreateDefaultSubobject<UOAGDPlaybackComponent>(TEXT("Motion"));IK=CreateDefaultSubobject<UOAGDConstraintsComponent>(TEXT("Constraints"));
 GetMesh()->SetRelativeLocation(FVector(0,0,-90));GetMesh()->SetRelativeRotation(FRotator(0,-90,0));GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;GetMesh()->bEnableUpdateRateOptimizations=false;GetMesh()->SetCanEverAffectNavigation(false);GetCapsuleComponent()->SetCanEverAffectNavigation(false);
 auto* C=GetCharacterMovement();C->bTickBeforeOwner=false;C->bOrientRotationToMovement=false;C->MaxWalkSpeed=35;C->MaxAcceleration=10000;C->BrakingDecelerationWalking=10000;
 CameraArm->bInheritYaw=false;CameraArm->bDoCollisionTest=false;CameraArm->TargetArmLength=650;CameraArm->SetRelativeRotation(FRotator(-45,140,0));FollowCamera->SetFieldOfView(65);
}
FString ACombinedPlayer::Unique(const FString& K){return K+TEXT(":")+FString::FromInt(++Serial);}
void ACombinedPlayer::BeginPlay(){
 Super::BeginPlay();Started=FPlatformTime::Seconds();GetCharacterMovement()->AddTickPrerequisiteActor(this);
 FParse::Value(FCommandLine::Get(),TEXT("CombinedReport="),Report);FParse::Value(FCommandLine::Get(),TEXT("CombinedMode="),Mode);SaveDirectory=FPaths::ProjectSavedDir()/TEXT("Combined");FParse::Value(FCommandLine::Get(),TEXT("CombinedSaveDir="),SaveDirectory);
 auto Config=ReadJson(Data(TEXT("project-config.json")));Store=MakeUnique<FOAGDStore>(SaveDirectory,Config->GetStringField(TEXT("id")),1);
 FString Error;Check(Router->LoadProfile(Data(TEXT("input-profile.json")),Error),TEXT("input profile configured"));Router->ActionChanged.AddDynamic(this,&ACombinedPlayer::Action);Router->PauseChanged.AddDynamic(this,&ACombinedPlayer::PauseChanged);
 Scenes->Prepared.AddDynamic(this,&ACombinedPlayer::Prepared);Scenes->Completed.AddDynamic(this,&ACombinedPlayer::Completed);
 TMap<FName,FOAGDFeedbackCue> Cues;auto Profile=ReadJson(Data(TEXT("feedback-profile.json")));
 for(const auto& Row:Profile->GetObjectField(TEXT("cues"))->Values){auto O=Row.Value->AsObject();FOAGDFeedbackCue C;C.UI=O->GetStringField(TEXT("domain"))==TEXT("ui");C.Loop=O->GetBoolField(TEXT("loop"));C.Spatial=O->GetBoolField(TEXT("spatial"));C.ReplaceOldest=O->GetStringField(TEXT("overflow"))==TEXT("oldest");C.Duration=O->GetNumberField(TEXT("duration"));C.Volume=O->GetNumberField(TEXT("volume"));C.Camera=O->GetNumberField(TEXT("camera"));C.Limit=O->GetNumberField(TEXT("limit"));auto Tint=O->GetArrayField(TEXT("color"));C.Color=FLinearColor(Tint[0]->AsNumber(),Tint[1]->AsNumber(),Tint[2]->AsNumber());C.Sound=LoadObject<USoundBase>(nullptr,*(FString(TEXT("/Game/Feedback/"))+Row.Key+TEXT(".")+Row.Key));if(!O->GetStringField(TEXT("visual")).IsEmpty())C.Visual=ACombinedPulse::StaticClass();Cues.Add(FName(*Row.Key),C);}
 Check(Feedback->Configure(Cues,8,Error),TEXT("feedback resources configured"));Feedback->Lifecycle.AddDynamic(this,&ACombinedPlayer::FeedbackEvent);Interaction->Configure(250,65);Interaction->Lifecycle.AddDynamic(this,&ACombinedPlayer::InteractionEvent);Nav->Configure(70,25,2,20);Nav->Lifecycle.AddDynamic(this,&ACombinedPlayer::NavigationEvent);
 FActorSpawnParameters Spawn;Spawn.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;Npc=GetWorld()->SpawnActor<ACombinedNpc>(FVector(-100,-900,93),FRotator::ZeroRotator,Spawn);Npc->GetCharacterMovement()->bRunPhysicsWithNoController=true;Npc->GetCharacterMovement()->MaxWalkSpeed=70;Npc->GetCharacterMovement()->AddTickPrerequisiteActor(this);Npc->GetCapsuleComponent()->SetCanEverAffectNavigation(false);Npc->GetMesh()->SetCanEverAffectNavigation(false);auto* N=Box(GetWorld(),FVector::ZeroVector,FVector(50,50,130),FLinearColor(.2,.7,.8));N->AttachToActor(Npc,FAttachmentTransformRules::KeepRelativeTransform);N->SetActorRelativeLocation(FVector(0,0,-25));
 GetMesh()->SetSkeletalMesh(LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/Playback/idle/idle.idle")));Motion->Bindings=LoadObject<UOAGDPlaybackSet>(nullptr,TEXT("/Game/Playback/Bindings.Bindings"));GetMesh()->SetAnimInstanceClass(LoadClass<UAnimInstance>(nullptr,TEXT("/Game/Playback/ABP_Player.ABP_Player_C")));
 Check(Motion->Bindings&&Motion->Validate(),TEXT("native animation configured"));Check(Motion->Bindings&&IK->Configure(GetMesh(),Motion->Bindings->ConstraintsJson),TEXT("native contact solver configured"));
 if(!Failures.IsEmpty()){Finish();return;}Message=Transition(Defaults());Check(Message.IsEmpty(),TEXT("initial native scene requested"));
}
void ACombinedPlayer::EndPlay(const EEndPlayReason::Type R){Cleanup();Super::EndPlay(R);}
bool ACombinedController::InputKey(const FInputKeyEventArgs& Args){if(auto* P=Cast<ACombinedPlayer>(GetPawn()))if(P->Router->HandleInput(Args))return true;return Super::InputKey(Args);}
void ACombinedPlayer::Action(FName Id,float Value){if(Value<=0){if(Id==TEXT("act"))Interaction->Cancel(TEXT("released"));return;}if(Id==TEXT("pause")){Menu=!Menu;Router->SetPause(TEXT("menu"),Menu);}else if(Id==TEXT("act"))Interaction->Begin(Unique(TEXT("take")));else if(Id==TEXT("cancel"))Cancel();else if(Id==TEXT("save"))Message=SaveGame();else if(Id==TEXT("load"))Message=LoadGame();else if(Id==TEXT("restart"))RestartGame();else if(Id==TEXT("scene"))Message=Transition(Defaults(Room==TEXT("a")?TEXT("b"):TEXT("a")));}
void ACombinedPlayer::PauseChanged(bool Value){Feedback->SetGamePaused(Value);Interaction->SetSuspended(Value);Nav->SetSuspended(Value);Router->SetContext(Value?TEXT("ui"):TEXT("game"));GetCharacterMovement()->StopMovementImmediately();Npc->GetCharacterMovement()->StopMovementImmediately();GetCharacterMovement()->SetComponentTickEnabled(!Value);Npc->GetCharacterMovement()->SetComponentTickEnabled(!Value);GetMesh()->SetComponentTickEnabled(!Value);}
void ACombinedPlayer::Cleanup(){Interaction->Clear();Nav->Clear();Feedback->Clear();IK->Reset();Held=false;Motion->Reset(TEXT("idle"));}
void ACombinedPlayer::Cancel(){Interaction->Cancel(TEXT("project-cancel"));Nav->Cancel(TEXT("project-cancel"));Feedback->StopScope(TEXT("action"));IK->Release();Held=false;Motion->Reset(TEXT("idle"));if(IsValid(Prop))Prop->SetActorLocation(GetActorLocation()+FVector(100,0,10));}
void ACombinedPlayer::ResetTarget(){if(IsValid(Prop))Prop->Destroy();Prop=Box(GetWorld(),FVector(100,-800,100),FVector(8,38,6),FLinearColor(.84,.6,.22));Target=NewObject<UCombinedTarget>(Prop);Target->StableId=TEXT("carry-tool");Target->Prompt=TEXT("Hold E: carry tool");Target->HoldSeconds=.4;Target->RegisterComponent();Interaction->RegisterTarget(Target);}
bool ACombinedPlayer::Take(){if(Router->IsPaused()||Held||!IsValid(Prop))return false;Motion->Select(TEXT("hold"));if(!IK->Take(Prop->GetStaticMeshComponent(),true))return false;Held=true;Feedback->Play(TEXT("door"),Unique(TEXT("pickup")),this,FVector(0,0,-85),true,TEXT("scene"),.4);Feedback->Play(TEXT("zone"),Unique(TEXT("carry")),this,FVector(0,0,-90),true,TEXT("action"),.5);return true;}
TSharedPtr<FJsonObject> ACombinedPlayer::Defaults(const FString& RoomId,bool IsHeld){auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("room"),RoomId);O->SetArrayField(TEXT("position"),{Num(-8),Num(.03),Num(0)});O->SetBoolField(TEXT("held"),IsHeld);return O;}
bool ACombinedPlayer::ValidState(const TSharedPtr<FJsonObject>& O){
 FString Id;bool H;const TArray<TSharedPtr<FJsonValue>>* P=nullptr;if(!O||!O->TryGetStringField(TEXT("room"),Id)||(Id!=TEXT("a")&&Id!=TEXT("b"))||!O->TryGetBoolField(TEXT("held"),H)||!O->TryGetArrayField(TEXT("position"),P)||P->Num()!=3)return false;
 double X[3];for(int I=0;I<3;++I)if(!(*P)[I]->TryGetNumber(X[I])||!FMath::IsFinite(X[I]))return false;return X[0]>=-10.5&&X[0]<=-5.5&&X[1]>=0&&X[1]<=2&&FMath::Abs(X[2])<=2.5;
}
TSharedPtr<FJsonObject> ACombinedPlayer::State()const{auto O=Defaults(Room,Held);auto P=GetActorLocation()-FVector(0,0,90);P.Z=FMath::Max(0.,P.Z);O->SetArrayField(TEXT("position"),Source(P));return O;}
FString ACombinedPlayer::Transition(const TSharedPtr<FJsonObject>& O){if(Busy)return TEXT("transition busy");if(!ValidState(O))return TEXT("invalid project state");FString Error;if(!Scenes->Stage(TEXT("/Game/Combined/Room_")+O->GetStringField(TEXT("room")),Error))return Error;Pending=O;Busy=true;Router->SetPause(TEXT("transition"),true);return TEXT("");}
void ACombinedPlayer::Prepared(bool Ok,FString Detail){if(!Ok){Message=Detail;Busy=false;Pending.Reset();Router->SetPause(TEXT("transition"),false);return;}Cleanup();FString Error;if(!Scenes->Commit(Error)){Message=Error;Busy=false;Pending.Reset();Router->SetPause(TEXT("transition"),false);}}
void ACombinedPlayer::Completed(bool Ok,FString Detail){if(Ok&&Pending){Room=Pending->GetStringField(TEXT("room"));ResetMotor(V(Pending->GetArrayField(TEXT("position")))+FVector(0,0,90));SetActorRotation(FRotator::ZeroRotator);Npc->ResetMotor(FVector(-100,-900,93));ResetTarget();if(Pending->GetBoolField(TEXT("held"))){Motion->Select(TEXT("hold"));Held=IK->Take(Prop->GetStaticMeshComponent(),true);}}else Message=Detail;Busy=false;Pending.Reset();Router->SetPause(TEXT("transition"),false);}
FString ACombinedPlayer::SaveGame(){if(Busy)return TEXT("transition busy");auto O=State();if(!ValidState(O))return TEXT("player outside this example's save region");FString Error;Store->Write(TEXT("slot1"),O,Error);return Error;}
FString ACombinedPlayer::LoadGame(){TSharedPtr<FJsonObject> O;FString Error;bool Recovered=false;if(!Store->Read(TEXT("slot1"),O,Recovered,Error))return Error;return Transition(O);}
void ACombinedPlayer::RestartGame(){Message=Transition(Defaults());}
void ACombinedPlayer::FeedbackEvent(int32 Handle,FString Event,FName Cue,FString Value){auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("kind"),TEXT("feedback"));O->SetNumberField(TEXT("handle"),Handle);O->SetStringField(TEXT("event"),Event);O->SetStringField(TEXT("cue"),Cue.ToString());O->SetStringField(TEXT("state"),Value);Events.Add(MakeShared<FJsonValueObject>(O));}
void ACombinedPlayer::InteractionEvent(FString Request,FString Id,FString Value,FString Why){auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("kind"),TEXT("interaction"));O->SetStringField(TEXT("request"),Request);O->SetStringField(TEXT("id"),Id);O->SetStringField(TEXT("state"),Value);O->SetStringField(TEXT("reason"),Why);Events.Add(MakeShared<FJsonValueObject>(O));}
void ACombinedPlayer::NavigationEvent(const FString& Request,const FString& Value,const FString& Why){auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("kind"),TEXT("navigation"));O->SetStringField(TEXT("request"),Request);O->SetStringField(TEXT("state"),Value);O->SetStringField(TEXT("reason"),Why);Events.Add(MakeShared<FJsonValueObject>(O));}
void ACombinedPlayer::Tick(float D){
 Super::Tick(D);if(Finished||!IK->Valid)return;Clock+=D;PhaseClock+=D;
 if(!Router->IsPaused()&&!Busy){
  FVector2D Wish=Report.IsEmpty()?FVector2D(Router->Strength(TEXT("forward"))-Router->Strength(TEXT("back")),Router->Strength(TEXT("right"))-Router->Strength(TEXT("left"))):TestWish;MoveWorld(Wish);if(!Wish.IsNearlyZero())SetActorRotation(FVector(Wish.X,Wish.Y,0).Rotation());
  Interaction->UpdateQuery(this,GetActorLocation()+FVector(0,0,10),GetActorForwardVector(),D);
  if(Patrol&&!Nav->Busy()&&Nav->ReadyMap()){PatrolSide=!PatrolSide;Nav->Request(Unique(TEXT("patrol")),Npc,FVector(-100,PatrolSide?-700:-900,0),nullptr,FVector(0,0,-90));}
  Nav->Step(D);if(Nav->DesiredVelocity.IsNearlyZero()){Npc->ConsumeMovementInputVector();Npc->GetCharacterMovement()->StopMovementImmediately();}else Npc->AddMovementInput(Nav->DesiredVelocity/70,1,true);
  Motion->Select(Held?(!Wish.IsNearlyZero()?TEXT("carry"):TEXT("hold")):(!Wish.IsNearlyZero()?TEXT("walk"):TEXT("idle")));FVector2D Stance(1,1);if(Motion->Current()==TEXT("walk")||Motion->Current()==TEXT("carry")){float T=FMath::Fmod(Motion->PositionSeconds,1);Stance=FVector2D(T>.1&&T<.4?1:0,T>.6&&T<.9?1:0);}IK->Prepare(D,GetCharacterMovement()->IsMovingOnGround(),Stance,Held);
 }
 FollowCamera->SetRelativeRotation(Feedback->CameraOffset);
 if(!Report.IsEmpty()){if(FPlatformTime::Seconds()-Started>120){Check(false,TEXT("combined test timeout"));Finish();}else TestStep(D);}
}
void ACombinedPlayer::Check(bool Ok,const FString& Name){Checks.Add(Str(Name));if(!Ok){Failures.Add(Str(Name));UE_LOG(LogTemp,Error,TEXT("COMBINED_FAIL %s"),*Name);}}
void ACombinedPlayer::Snapshot(const FString& Name){auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("name"),Name);O->SetObjectField(TEXT("state"),State());O->SetNumberField(TEXT("clock"),Motion->PositionSeconds);O->SetArrayField(TEXT("npc"),Source(Npc->GetActorLocation()-FVector(0,0,90)));O->SetNumberField(TEXT("feedback"),Feedback->Active.Num());O->SetStringField(TEXT("grip"),IK->Result.GripStatus);O->SetNumberField(TEXT("weight"),IK->Result.GripWeight);O->SetStringField(TEXT("navigation"),Nav->State);O->SetBoolField(TEXT("npc_tick"),Npc->GetCharacterMovement()->IsComponentTickEnabled());O->SetNumberField(TEXT("npc_mode"),Npc->GetCharacterMovement()->MovementMode);O->SetBoolField(TEXT("npc_without_controller"),Npc->GetCharacterMovement()->bRunPhysicsWithNoController);O->SetNumberField(TEXT("npc_role"),int(Npc->GetLocalRole()));O->SetStringField(TEXT("npc_updated"),GetNameSafe(Npc->GetCharacterMovement()->UpdatedComponent));O->SetNumberField(TEXT("npc_interval"),Npc->GetCharacterMovement()->GetComponentTickInterval());O->SetArrayField(TEXT("npc_velocity"),Source(Npc->GetVelocity()));Snapshots.Add(MakeShared<FJsonValueObject>(O));if(!FParse::Param(FCommandLine::Get(),TEXT("nullrhi")))FScreenshotRequest::RequestScreenshot(Report+TEXT("-")+Name+TEXT(".png"),false,false);}
void ACombinedPlayer::TestStep(float D){
 auto Next=[&]{++Phase;PhaseClock=0;};
 if(Busy)return;
 if(Mode==TEXT("resume")){
  if(Phase==0&&PhaseClock>1){Check(LoadGame().IsEmpty(),TEXT("separate process loads saved state"));Next();}
  else if(Phase==1&&PhaseClock>.8){Check(Room==TEXT("b")&&Held&&IK->Holding,TEXT("separate process restores room and actual grip"));Check(IK->Result.GripWeight>.9,TEXT("separate process native grip evaluated"));Check(Feedback->Active.IsEmpty(),TEXT("load does not replay transient feedback"));Snapshot(TEXT("resumed"));Next();}
  else if(Phase==2&&PhaseClock>.1)Finish();return;
 }
 switch(Phase){
 case 0:if(PhaseClock>1&&Nav->ReadyMap()){Check(Nav->Busy(),TEXT("native navigation active on generated replacement scene"));bool Found=false;for(TActorIterator<AActor> It(GetWorld());It;++It)for(auto Tag:It->Tags)if(Tag.ToString().Contains(TEXT("curve_a_portal")))Found=true;Check(Found,TEXT("native static replacement present"));SavedNpc=Npc->GetActorLocation();Next();}break;
 case 1:if(PhaseClock>.5){Snapshot(TEXT("patrol"));Check(FVector::Dist(SavedNpc,Npc->GetActorLocation())>15,TEXT("NPC moves through collision motor"));TArray<AActor*> Attached;Npc->GetAttachedActors(Attached);bool VisualSafe=!Attached.IsEmpty();for(auto* A:Attached){auto* Shape=Cast<UPrimitiveComponent>(A->GetRootComponent());VisualSafe&=Shape&&Shape->GetCollisionEnabled()==ECollisionEnabled::NoCollision;}Check(VisualSafe,TEXT("NPC decoration cannot block its movement capsule after attachment"));Check(Interaction->FocusedId()==TEXT("carry-tool"),TEXT("real spatial query focuses stable interaction"));Router->Feed(TEXT("E"),1);Next();}break;
 case 2:if(PhaseClock>.12){Check(Interaction->Holding(),TEXT("hold request in progress"));Router->SetPause(TEXT("menu"),true);Router->SetPause(TEXT("modal"),true);Check(!Interaction->Holding()&&!Held,TEXT("pause cancels incomplete interaction"));Router->SetPause(TEXT("menu"),false);Check(Router->IsPaused(),TEXT("nested pause remains active"));SavedClock=Motion->PositionSeconds;SavedPlayer=GetActorLocation();SavedNpc=Npc->GetActorLocation();Next();}break;
 case 3:if(PhaseClock>.4){Check(FMath::IsNearlyEqual(SavedClock,Motion->PositionSeconds)&&GetActorLocation().Equals(SavedPlayer)&&Npc->GetActorLocation().Equals(SavedNpc),TEXT("pause freezes player NPC and native animation"));Router->SetPause(TEXT("modal"),false);Next();}break;
 case 4:if(PhaseClock>.5){Check(!Held,TEXT("held input cannot resume cancelled interaction"));Router->Feed(TEXT("E"),0);Router->Feed(TEXT("E"),1);Next();}break;
 case 5:if(PhaseClock>.7){Router->Feed(TEXT("E"),0);Check(Held&&IK->Holding&&IK->Result.GripWeight>.9,TEXT("interaction commits to real two-hand grip"));Check(!Feedback->Active.IsEmpty(),TEXT("committed interaction owns native feedback"));bool Bound=!Feedback->Active.IsEmpty();for(const auto& Item:Feedback->Active){auto* Pulse=Cast<ACombinedPulse>(Item.Value.Visual);FLinearColor Value;Bound&=Pulse&&Pulse->Tint&&Pulse->Tint->GetVectorParameterValue(FMaterialParameterInfo(TEXT("Tint")),Value)&&Value.Equals(Feedback->Cues[Item.Value.Cue].Color,.001f)&&Pulse->Shape->GetRelativeLocation().Z>=8;}Check(Bound,TEXT("feedback visual uses declared native tint above the floor"));Snapshot(TEXT("holding"));Router->SetPause(TEXT("menu"),true);SavedClock=Motion->PositionSeconds;SavedProp=Prop->GetActorLocation();Ages.Empty();for(auto& Item:Feedback->Active)Ages.Add(Item.Key,Item.Value.Age);Next();}break;
 case 6:if(PhaseClock>.3){bool Frozen=true;for(auto& Item:Feedback->Active)Frozen&=Ages.Contains(Item.Key)&&FMath::IsNearlyEqual(Ages[Item.Key],Item.Value.Age);Check(Frozen&&FMath::IsNearlyEqual(SavedClock,Motion->PositionSeconds)&&Prop->GetActorLocation().Equals(SavedProp),TEXT("pause freezes feedback age animation and attached prop"));Check(Feedback->Play(TEXT("action"),Unique(TEXT("paused")),this,FVector::ZeroVector,true,TEXT("scene"))==-1,TEXT("paused game cue rejected"));Router->SetPause(TEXT("menu"),false);TestWish=FVector2D(1,0);Next();}break;
 case 7:if(PhaseClock>.6){Check(FVector::Dist(GetActorLocation(),SavedPlayer)>15&&Held,TEXT("carrying moves through native motor"));Check(Motion->Current()==TEXT("carry"),TEXT("carry animation selected while moving"));TestWish=FVector2D::ZeroVector;Patrol=false;Cancel();Next();}break;
 case 8:if(PhaseClock>.2){Check(!Held&&!IK->Holding&&IK->Result.GripWeight==0,TEXT("cancel releases native hand constraint"));Check(Feedback->Active.IsEmpty()&&!Interaction->Holding()&&!Nav->Busy(),TEXT("cancel clears cross-module transient work"));PreviousScene=Scenes->Current;auto Bad=Defaults(TEXT("missing"));Check(!Transition(Bad).IsEmpty()&&Scenes->Current==PreviousScene.Get(),TEXT("invalid destination leaves current scene intact"));FString Error;Check(!Scenes->Stage(TEXT("/Game/Missing"),Error)&&Scenes->Current==PreviousScene.Get(),TEXT("missing native scene leaves current scene intact"));Check(Scenes->Stage(TEXT("/Game/Combined/Room_b"),Error),TEXT("scene candidate prepared"));Check(Scenes->Cancel()&&!Scenes->Staged&&Scenes->Current==PreviousScene.Get(),TEXT("staged scene cancellation preserves current world"));RestartGame();Next();}break;
 case 9:if(PhaseClock>.4){Router->Feed(TEXT("E"),1);Next();}break;
 case 10:if(PhaseClock>.7){Router->Feed(TEXT("E"),0);Check(Held,TEXT("interaction can restart after cancellation"));PreviousScene=Scenes->Current;Check(Transition(Defaults(TEXT("b"))).IsEmpty(),TEXT("native scene switch commits"));Next();}break;
 case 11:if(PhaseClock>.6){Check((!PreviousScene.IsValid()||!PreviousScene->IsLevelVisible())&&Room==TEXT("b"),TEXT("previous native scene no longer visible"));Check(!Held&&!IK->Holding&&Feedback->Active.IsEmpty()&&!Interaction->Holding(),TEXT("scene switch releases grip feedback and pending interaction"));Check(Interaction->FocusedId()==TEXT("carry-tool"),TEXT("new scene re-registers stable target"));Router->Feed(TEXT("E"),1);Next();}break;
 case 12:if(PhaseClock>.7){Router->Feed(TEXT("E"),0);Check(SaveGame().IsEmpty(),TEXT("project state written to local journal"));Check(Held&&Room==TEXT("b"),TEXT("saved state contains room and stable held state"));RestartGame();Next();}break;
 case 13:if(PhaseClock>.4){Check(Room==TEXT("a")&&!Held&&Feedback->Active.IsEmpty(),TEXT("restart returns clean project defaults"));Check(LoadGame().IsEmpty(),TEXT("saved state applied through scene transaction"));Next();}break;
 case 14:if(PhaseClock>.8){Check(Room==TEXT("b")&&Held&&IK->Result.GripWeight>.9,TEXT("load restores room and evaluated grip"));Check(Feedback->Active.IsEmpty()&&!Interaction->Holding(),TEXT("load excludes transient feedback and requests"));Check(LoadGame().IsEmpty(),TEXT("repeated load accepted"));Next();}break;
 case 15:if(PhaseClock>.6){Check(Feedback->Active.IsEmpty()&&Held,TEXT("repeated load has no duplicate cue"));FString Error;auto Bad=Defaults(TEXT("unknown"));Check(Store->Write(TEXT("bad"),Bad,Error),TEXT("invalid project payload fixture saved separately"));PreviousScene=Scenes->Current;TSharedPtr<FJsonObject> Read;bool Recovered;Store->Read(TEXT("bad"),Read,Recovered,Error);Check(!Transition(Read).IsEmpty()&&Scenes->Current==PreviousScene.Get()&&Held,TEXT("invalid saved project payload rejected before mutation"));Patrol=true;Next();}break;
 case 16:if(PhaseClock>.7){Check(Nav->Busy(),TEXT("NPC resumes patrol after load"));Snapshot(TEXT("restored"));Next();}break;
 case 17:if(PhaseClock>.1)Finish();break;
 }
}
void ACombinedPlayer::Finish(){if(Finished)return;Finished=true;auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("schema"),TEXT("oagd.combined-runtime/1"));O->SetStringField(TEXT("engine"),FEngineVersion::Current().ToString());O->SetStringField(TEXT("mode"),Mode);O->SetArrayField(TEXT("checks"),Checks);O->SetArrayField(TEXT("failures"),Failures);O->SetArrayField(TEXT("events"),Events);O->SetArrayField(TEXT("snapshots"),Snapshots);O->SetBoolField(TEXT("human_playtest"),false);FString Text;FJsonSerializer::Serialize(O,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*Report);FGenericPlatformMisc::RequestExitWithStatus(false,Failures.IsEmpty()?0:1);}
ACombinedGame::ACombinedGame(){DefaultPawnClass=ACombinedPlayer::StaticClass();PlayerControllerClass=ACombinedController::StaticClass();HUDClass=ACombinedHUD::StaticClass();}
void ACombinedGame::BeginPlay(){Super::BeginPlay();for(float Yaw:{0.f,90.f,180.f,270.f}){auto* Light=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,600),FRotator(-35,Yaw,0));Light->GetLightComponent()->SetMobility(EComponentMobility::Movable);Light->GetLightComponent()->SetIntensity(1.2);Light->GetLightComponent()->SetCastShadows(false);}}
void ACombinedHUD::DrawHUD(){Super::DrawHUD();if(auto* P=Cast<ACombinedPlayer>(GetOwningPawn()))DrawText(FString::Printf(TEXT("Combined example | UE 5.8 | Room %s | %s\nWASD move / hold E take / Q cancel / Esc pause\nK save / L load / Tab room / R restart\n%s | NPC: %s | held: %s\n%s"),*P->Room,P->Router->IsPaused()?TEXT("PAUSED"):TEXT("PLAYING"),*P->Interaction->Prompt,*P->Nav->State,P->Held?TEXT("yes"):TEXT("no"),*P->Message),FLinearColor::White,18,18,nullptr,1.3);}
