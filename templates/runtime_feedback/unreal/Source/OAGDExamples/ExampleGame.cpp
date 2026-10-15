#include "ExampleGame.h"
#include "Components/AudioComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundWave.h"
#include "AudioMixerBlueprintLibrary.h"
#include <limits>
#include "Misc/App.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/GameUserSettings.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LevelStreamingDynamic.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "UObject/ConstructorHelpers.h"
#include "Misc/EngineVersion.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"
#include "UnrealClient.h"
#include "Modules/ModuleManager.h"
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl,OAGDExamples,"OAGDExamples");
 AFeedbackRing::AFeedbackRing(){VisualMesh=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pulse"));RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));VisualMesh->SetupAttachment(RootComponent);VisualMesh->SetMobility(EComponentMobility::Movable);VisualMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);static ConstructorHelpers::FObjectFinder<UStaticMesh> Shape(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));VisualMesh->SetStaticMesh(Shape.Object);PrimaryActorTick.bCanEverTick=false;}
 void AFeedbackRing::Sample_Implementation(float Age,float Strength,FLinearColor Color){
  if(!Tint){auto* Material=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Feedback/FeedbackTint.FeedbackTint"));if(Material){Tint=UMaterialInstanceDynamic::Create(Material,this);VisualMesh->SetMaterial(0,Tint);}}
  const float Phase=FMath::Fmod(Age,1.f),Size=(1.f+Phase*1.3f)*FMath::Max(.1f,Strength);VisualMesh->SetRelativeScale3D(FVector(Size,Size,.04));VisualMesh->SetRelativeLocation(FVector(0,0,12+FMath::Sin(Age*4)*4));if(Tint)Tint->SetVectorParameterValue(TEXT("Tint"),Color*(1-Phase*.45f));
 }
namespace {
 TSharedPtr<FJsonObject> Clone(const TSharedPtr<FJsonObject>& Value){FString Text;FJsonSerializer::Serialize(Value.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));TSharedPtr<FJsonObject> Copy;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Copy);return Copy;}
 void Position(const TSharedPtr<FJsonObject>& Data,FVector Value){Data->SetArrayField(TEXT("player"),{MakeShared<FJsonValueNumber>(Value.X),MakeShared<FJsonValueNumber>(Value.Y),MakeShared<FJsonValueNumber>(Value.Z)});}
 FVector Position(const TSharedPtr<FJsonObject>& Data){const auto& A=Data->GetArrayField(TEXT("player"));return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());}
}
class SStateMenuRoot : public SCompoundWidget {
public:
 SLATE_BEGIN_ARGS(SStateMenuRoot){} SLATE_ARGUMENT(TWeakObjectPtr<AStateController>,Controller) SLATE_DEFAULT_SLOT(FArguments,Content) SLATE_END_ARGS()
 void Construct(const FArguments& Args){Controller=Args._Controller;ChildSlot[Args._Content.Widget];}
 virtual FReply OnPreviewKeyDown(const FGeometry&,const FKeyEvent& Event)override{return Forward(Event,true);}
 virtual FReply OnKeyUp(const FGeometry&,const FKeyEvent& Event)override{return Forward(Event,false);}
private:
 TWeakObjectPtr<AStateController> Controller;
 FReply Forward(const FKeyEvent& Event,bool Down){if(Controller.IsValid()){FInputKeyEventArgs Args(nullptr,Event.GetInputDeviceId(),Event.GetKey(),Down?(Event.IsRepeat()?IE_Repeat:IE_Pressed):IE_Released,FPlatformTime::Cycles64());if(Controller->InputKey(Args))return FReply::Handled();}return FReply::Unhandled();}
};
AStatePlayer::AStatePlayer(){auto* Visual=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));Visual->SetupAttachment(RootComponent);static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeAsset(TEXT("/Engine/BasicShapes/Cube.Cube"));Visual->SetStaticMesh(CubeAsset.Object);Visual->SetRelativeScale3D(FVector(.6,.6,1.6));Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);PrimaryActorTick.bCanEverTick=true;}
void AStatePlayer::Tick(float Delta){Super::Tick(Delta);if(auto* PC=Cast<AStateController>(Controller)){MoveWorld(FVector2D(PC->Router->Strength(TEXT("forward"))-PC->Router->Strength(TEXT("back")),PC->Router->Strength(TEXT("right"))-PC->Router->Strength(TEXT("left"))));}}
AExampleGame::AExampleGame(){DefaultPawnClass=AStatePlayer::StaticClass();PlayerControllerClass=AStateController::StaticClass();}
void AExampleGame::BeginPlay(){Super::BeginPlay();auto* Light=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,500),FRotator(-55,-30,0));Light->GetLightComponent()->SetMobility(EComponentMobility::Movable);Light->GetLightComponent()->SetIntensity(5.f);}
AStateController::AStateController(){Router=CreateDefaultSubobject<UOAGDInputComponent>(TEXT("InputRouter"));Scenes=CreateDefaultSubobject<UOAGDSceneComponent>(TEXT("Scenes"));Feedback=CreateDefaultSubobject<UOAGDFeedbackComponent>(TEXT("Feedback"));PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.bTickEvenWhenPaused=true;bShouldPerformFullTickWhenPaused=true;}
void AStateController::BeginPlay(){
 Super::BeginPlay();StartedAt=FPlatformTime::Seconds();Testing=FParse::Param(FCommandLine::Get(),TEXT("OAGDSelfTest"));Report=FPaths::ProjectSavedDir()/TEXT("state-validation.json");FParse::Value(FCommandLine::Get(),TEXT("FeedbackReport="),Report);TestPhase=TEXT("exercise");FParse::Value(FCommandLine::Get(),TEXT("StatePhase="),TestPhase);
 FString Error,ProfileText;FFileHelper::LoadFileToString(ProfileText,*(FPaths::ProjectContentDir()/TEXT("OAGDData/input-profile.json")));TSharedPtr<FJsonObject> Profile;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(ProfileText),Profile);
 if(!Profile.IsValid()||!Router->Configure(ProfileText,Error)){Check(false,TEXT("input profile readable"));Finish();return;}
 Identity=Profile->GetStringField(TEXT("id"));SaveRoot=FPaths::ProjectSavedDir()/TEXT("OAGDState")/Identity;FParse::Value(FCommandLine::Get(),TEXT("StateRoot="),SaveRoot);Store=MakeUnique<FOAGDStore>(SaveRoot,Identity);
 ScenePaths.Add(TEXT("a"),TEXT("/Game/Room_a"));ScenePaths.Add(TEXT("b"),TEXT("/Game/Room_b"));State=MakeShared<FJsonObject>();State->SetStringField(TEXT("scene"),TEXT("a"));State->SetStringField(TEXT("checkpoint"),TEXT("a-entry"));auto Objects=MakeShared<FJsonObject>();Objects->SetBoolField(TEXT("door-a"),false);Objects->SetBoolField(TEXT("door-b"),false);State->SetObjectField(TEXT("objects"),Objects);Position(State,FVector(0,0,100));
 Settings=FOAGDSettings::Defaults();TSharedPtr<FJsonObject> Saved;bool Recovered;if(Store->Read(TEXT("settings"),Saved,Recovered,Error)&&FOAGDSettings::Validate(Saved,Error)){Settings=Saved;if(Recovered)Notice=TEXT("Settings recovered from previous valid generation");}else if(Error!=TEXT("slot not found"))Notice=TEXT("Saved settings rejected; using defaults");FOAGDSettings::Apply(Settings,Error);
 Router->ActionChanged.AddDynamic(this,&AStateController::OnAction);Router->PauseChanged.AddDynamic(this,&AStateController::OnPause);Scenes->Prepared.AddDynamic(this,&AStateController::OnPrepared);Scenes->Completed.AddDynamic(this,&AStateController::OnCompleted);
 BuildUI();BeginFeedback();AddTickPrerequisiteComponent(Feedback);OpenMenu();if(!Transition(State,Error)){Check(false,Error);Finish();}
}
void AStateController::EndPlay(const EEndPlayReason::Type Reason){if(UI.IsValid()&&GetWorld()->GetGameViewport())GetWorld()->GetGameViewport()->RemoveViewportWidgetContent(UI.ToSharedRef());Focus.Clear();Super::EndPlay(Reason);}
bool AStateController::Validate(const TSharedPtr<FJsonObject>& Data,FString& Error)const{
 Error.Reset();FString Scene,Checkpoint;const TSharedPtr<FJsonObject>* Objects=nullptr;const TArray<TSharedPtr<FJsonValue>>* Values=nullptr;bool Open=false;
 if(!Data.IsValid()||Data->Values.Num()!=4||!Data->TryGetStringField(TEXT("scene"),Scene)||(Scene!=TEXT("a")&&Scene!=TEXT("b"))){Error=TEXT("unknown scene");return false;}
 if(!Data->TryGetStringField(TEXT("checkpoint"),Checkpoint)||(Checkpoint!=Scene+TEXT("-entry")&&Checkpoint!=Scene+TEXT("-door"))){Error=TEXT("checkpoint does not belong to scene");return false;}
 if(!Data->TryGetObjectField(TEXT("objects"),Objects)||(*Objects)->Values.Num()!=2||!(*Objects)->TryGetBoolField(TEXT("door-a"),Open)||!(*Objects)->TryGetBoolField(TEXT("door-b"),Open)){Error=TEXT("missing stable object IDs");return false;}
 if(!Data->TryGetArrayField(TEXT("player"),Values)||Values->Num()!=3){Error=TEXT("invalid player position");return false;}
 for(const auto& V:*Values){double N=0;if(!V->TryGetNumber(N)||!FMath::IsFinite(N)||FMath::Abs(N)>900){Error=TEXT("position outside playable bounds");return false;}}
 if((*Values)[2]->AsNumber()<0||(*Values)[2]->AsNumber()>500){Error=TEXT("invalid player height");return false;}return true;
}
TSharedPtr<FJsonObject> AStateController::Snapshot()const{auto Data=Clone(State);if(GetPawn())Position(Data,GetPawn()->GetActorLocation());return Data;}
AActor* AStateController::Door(ULevelStreamingDynamic* Level,const FString& Scene)const{if(!Level||!Level->GetLoadedLevel())return nullptr;AActor* Found=nullptr;const FName Id(*(TEXT("door-")+Scene));for(const auto& Actor:Level->GetLoadedLevel()->Actors)if(Actor&&Actor->Tags.Contains(Id)){if(Found)return nullptr;Found=Actor;}return Found;}
bool AStateController::ApplyObjects(ULevelStreamingDynamic* Level,const TSharedPtr<FJsonObject>& Data,FString& Error){auto* Target=Door(Level,Data->GetStringField(TEXT("scene")));if(!Target){Error=TEXT("scene stable door ID missing or duplicated");return false;}const bool Open=Data->GetObjectField(TEXT("objects"))->GetBoolField(TEXT("door-")+Data->GetStringField(TEXT("scene")));Target->SetActorHiddenInGame(Open);Target->SetActorEnableCollision(!Open);return true;}
bool AStateController::Transition(const TSharedPtr<FJsonObject>& Data,FString& Error){if(Busy){Error=TEXT("transition busy");return false;}if(!Validate(Data,Error))return false;Pending=Clone(Data);Busy=true;Router->SetPause(TEXT("transition"),true);if(!Scenes->Stage(ScenePaths[Data->GetStringField(TEXT("scene"))],Error)){Pending.Reset();Busy=false;Router->SetPause(TEXT("transition"),false);return false;}return true;}
void AStateController::OnPrepared(bool Success,FString Detail){FString Error;if(!Success||!ApplyObjects(Scenes->Staged,Pending,Error)){Scenes->Cancel();Message=Error.IsEmpty()?Detail:Error;return;}if(!Scenes->Commit(Error)){Scenes->Cancel();Message=Error;}}
void AStateController::OnCompleted(bool Success,FString Detail){if(Success){Feedback->StopScope(TEXT("scene"));ZoneInside=false;ZoneHandle=-1;State=Pending;FString Error;ApplyObjects(Scenes->Current,State,Error);if(auto* PawnActor=Cast<AStatePlayer>(GetPawn()))PawnActor->ResetMotor(Position(State));}Pending.Reset();Busy=false;Router->SetPause(TEXT("transition"),false);Message=Detail;}
bool AStateController::SaveGame(const FString& Slot,const TSharedPtr<FJsonObject>& Data,FString& Error){if(Busy){Error=TEXT("transition busy");return false;}return Validate(Data,Error)&&Store->Write(Slot,Data,Error);}
bool AStateController::LoadGame(const FString& Slot,FString& Error){if(Busy){Error=TEXT("transition busy");return false;}TSharedPtr<FJsonObject> Data;bool Recovered;if(!Store->Read(Slot,Data,Recovered,Error))return false;const bool Ok=Transition(Data,Error);if(Ok&&Recovered)Notice=TEXT("Recovered previous valid generation");return Ok;}
bool AStateController::ApplySettings(const TSharedPtr<FJsonObject>& Data,FString& Error){if(!FOAGDSettings::Validate(Data,Error)||!Store->Write(TEXT("settings"),Data,Error)||!FOAGDSettings::Apply(Data,Error))return false;Settings=Clone(Data);return true;}
bool AStateController::InputKey(const FInputKeyEventArgs& Args){if(!MenuOpen&&!Busy&&Args.Key==EKeys::MouseX){Orbit(Args.AmountDepressed);return true;}if(Router&&Router->HandleInput(Args))return true;return Super::InputKey(Args);}
void AStateController::Orbit(float Delta){if(auto* PawnActor=Cast<AStatePlayer>(GetPawn()))PawnActor->Orbit(FVector2D(Delta*Settings->GetNumberField(TEXT("camera_sensitivity")),0));}
void AStateController::OnPause(bool Value){Feedback->SetGamePaused(Value);if(auto* PawnActor=Cast<AStatePlayer>(GetPawn())){PawnActor->ConsumeMovementInputVector();PawnActor->GetCharacterMovement()->StopMovementImmediately();}SetPause(Value);}
void AStateController::OpenMenu(){Router->SetContext(TEXT("ui"));Router->SetPause(TEXT("menu"),true);MenuOpen=true;Menu->SetVisibility(EVisibility::Visible);Selection=0;FInputModeGameAndUI Mode;Mode.SetWidgetToFocus(Buttons[0]);Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);Mode.SetHideCursorDuringCapture(false);SetInputMode(Mode);Focus.Push(Buttons[0].ToSharedRef());bShowMouseCursor=true;}
void AStateController::CloseMenu(){MenuOpen=false;Menu->SetVisibility(EVisibility::Collapsed);Focus.Pop();Router->SetContext(TEXT("game"));Router->SetPause(TEXT("menu"),false);FInputModeGameOnly Mode;SetInputMode(Mode);bShowMouseCursor=false;}
void AStateController::Select(int32 Index){Selection=(Index+Buttons.Num())%Buttons.Num();FSlateApplication::Get().SetKeyboardFocus(Buttons[Selection],EFocusCause::SetDirectly);}
void AStateController::Choose(int32 Index){if(Busy)return;FString Error;
 if(Index==1&&MenuOpen)CloseMenu();
 if(Index==5){if(MenuOpen)CloseMenu();Feedback->Play(TEXT("action"),EventId(TEXT("action")),GetPawn(),FVector(0,0,-70),true,TEXT("scene"));return;}
 if(Index==6){if(MenuOpen)CloseMenu();if(auto* PawnActor=Cast<AStatePlayer>(GetPawn()))PawnActor->ResetMotor(FVector(ZoneInside?0:500,0,100));return;}

 if(Index==0)CloseMenu();
 else if(Index==1){auto Objects=State->GetObjectField(TEXT("objects"));const FString Id=TEXT("door-")+State->GetStringField(TEXT("scene"));Objects->SetBoolField(Id,!Objects->GetBoolField(Id));ApplyObjects(Scenes->Current,State,Error);Feedback->Play(TEXT("door"),EventId(TEXT("door")),nullptr,Door(Scenes->Current,State->GetStringField(TEXT("scene")))->GetActorLocation(),false,TEXT("scene"));}
 else if(Index==2){auto Data=Snapshot();const FString NextScene=State->GetStringField(TEXT("scene"))==TEXT("a")?TEXT("b"):TEXT("a");Data->SetStringField(TEXT("scene"),NextScene);Data->SetStringField(TEXT("checkpoint"),NextScene+TEXT("-entry"));Position(Data,FVector(0,0,100));Transition(Data,Error);}
 else if(Index==3)SaveGame(TEXT("slot1"),Snapshot(),Error);
 else if(Index==4)LoadGame(TEXT("slot1"),Error);
 else if(Index==5){auto Data=Snapshot();Data->SetStringField(TEXT("checkpoint"),Data->GetStringField(TEXT("scene"))+TEXT("-door"));if(SaveGame(TEXT("checkpoint"),Data,Error))State->SetStringField(TEXT("checkpoint"),Data->GetStringField(TEXT("checkpoint")));}
 else if(Index==6)LoadGame(TEXT("checkpoint"),Error);
 else if(Index==7){auto Data=Clone(Settings);Data->SetNumberField(TEXT("fps"),Settings->GetNumberField(TEXT("fps"))==60?120:60);Data->SetNumberField(TEXT("camera_sensitivity"),Settings->GetNumberField(TEXT("camera_sensitivity"))==1?2:1);ApplySettings(Data,Error);}
 else if(Index==8){auto Data=Clone(Settings);Data->SetBoolField(TEXT("vsync"),!Settings->GetBoolField(TEXT("vsync")));ApplySettings(Data,Error);}
 else if(Index==9)ApplySettings(FOAGDSettings::Defaults(),Error);
 else if(Index==10)UKismetSystemLibrary::QuitGame(this,this,EQuitPreference::Quit,false);
 if(Index!=1&&Index!=10)Feedback->Play(TEXT("ui"),EventId(TEXT("ui")),nullptr,FVector::ZeroVector,false,TEXT("ui"));if(!Busy)Message=Error.IsEmpty()?TEXT("Completed"):Error;
}
void AStateController::OnAction(FName Action,float Value){if(Value<.5||Busy)return;if(MenuOpen){auto Current=FSlateApplication::Get().GetKeyboardFocusedWidget();for(int32 I=0;I<Buttons.Num();++I)if(Current==Buttons[I])Selection=I;}if(Action==TEXT("pause")){if(MenuOpen)CloseMenu();else OpenMenu();}else if(Action==TEXT("act"))Choose(1);else if(Action==TEXT("ui_up"))Select(Selection-1);else if(Action==TEXT("ui_down"))Select(Selection+1);else if(Action==TEXT("ui_accept"))Choose(Selection);else if(Action==TEXT("ui_back"))CloseMenu();}
void AStateController::BuildUI(){auto Column=SNew(SVerticalBox);Column->AddSlot().AutoHeight().Padding(20)[SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Bold",18)).Text_Lambda([this]{return FText::FromString(FString::Printf(TEXT("Feedback feedback | UE 5.8 | Room %s | %s | Door open: %s\nWASD move | Space toggle door | Esc menu | Mouse look\nFPS %.0f | Camera %.1f | %s\n%s"),*State->GetStringField(TEXT("scene")),*State->GetStringField(TEXT("checkpoint")),State->GetObjectField(TEXT("objects"))->GetBoolField(TEXT("door-")+State->GetStringField(TEXT("scene")))?TEXT("yes"):TEXT("no"),Settings->GetNumberField(TEXT("fps")),Settings->GetNumberField(TEXT("camera_sensitivity")),*Message,*Notice));})];SAssignNew(Menu,SVerticalBox);
 const TCHAR* Names[]={TEXT("Resume / Start"),TEXT("Toggle this room's door"),TEXT("Switch room A / B"),TEXT("Save slot 1"),TEXT("Continue from slot 1"),TEXT("Action feedback (attached to player)"),TEXT("Enter / leave feedback zone"),TEXT("Settings: cycle FPS / camera sensitivity"),TEXT("Toggle VSync"),TEXT("Restore default settings"),TEXT("Quit")};
 for(int32 I=0;I<11;++I){TSharedPtr<SButton> Button;Menu->AddSlot().AutoHeight().Padding(3)[SAssignNew(Button,SButton).ContentPadding(FMargin(14,6)).IsEnabled_Lambda([this]{return !Busy;}).OnClicked_Lambda([this,I]{Choose(I);return FReply::Handled();})[SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Regular",17)).Text(FText::FromString(Names[I]))]];Buttons.Add(Button);}
 Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(12)[SNew(SBox).WidthOverride(540)[SNew(SBorder).Padding(12)[Menu.ToSharedRef()]]];UI=SNew(SStateMenuRoot).Controller(this)[Column];GetWorld()->GetGameViewport()->AddViewportWidgetContent(UI.ToSharedRef(),10);
}
void AStateController::Check(bool Ok,const FString& Name){Checks.Add(Name);if(!Ok)Failures.Add(Name);}
void AStateController::Tick(float Delta){Super::Tick(Delta);CheckZone();if(auto* PawnActor=Cast<AStatePlayer>(GetPawn())){auto Rotation=PawnActor->CameraArm->GetRelativeRotation();PawnActor->CameraArm->SetRelativeRotation(Rotation-PreviousCamera+Feedback->CameraOffset);PreviousCamera=Feedback->CameraOffset;PeakCamera=FMath::Max(PeakCamera,float(PreviousCamera.Euler().Size()));}if(Testing&&!Finished){if(FPlatformTime::Seconds()-StartedAt>120){Check(false,TEXT("native case exceeded 120 seconds"));Finish();return;}if(!Busy){++Frame;TestStep();}}}
void AStateController::Finish(){Finished=true;auto Root=MakeShared<FJsonObject>();Root->SetStringField(TEXT("engine"),FEngineVersion::Current().ToString());Root->SetStringField(TEXT("phase"),TestPhase);Root->SetBoolField(TEXT("no_animation_plugin"),true);Root->SetStringField(TEXT("input"),TEXT("Project events and native consumers; no human listening claim"));Root->SetArrayField(TEXT("events"),Events);Root->SetStringField(TEXT("audio"),Report+TEXT(".wav"));Root->SetNumberField(TEXT("app_audio_volume"),FApp::GetVolumeMultiplier());TArray<TSharedPtr<FJsonValue>> C,F;for(const auto& S:Checks)C.Add(MakeShared<FJsonValueString>(S));for(const auto& S:Failures)F.Add(MakeShared<FJsonValueString>(S));Root->SetArrayField(TEXT("checks"),C);Root->SetArrayField(TEXT("failures"),F);FString Text;FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*Report,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);FPlatformMisc::RequestExitWithStatus(false,Failures.Num()?1:0);}

void AStateController::BeginFeedback(){
 FString Text,Error;TSharedPtr<FJsonObject> Config;TMap<FName,FOAGDFeedbackCue> Bindings;
 if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("OAGDData/feedback-profile.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Config)||!Config.IsValid()){Check(false,TEXT("feedback profile readable"));Finish();return;}
 const TSharedPtr<FJsonObject>* Specs=nullptr;double Budget=0,Schema=0;
 if(!Config->TryGetNumberField(TEXT("schema"),Schema)||Schema!=1||!Config->TryGetObjectField(TEXT("cues"),Specs)||!Config->TryGetNumberField(TEXT("max_active"),Budget)||Budget!=FMath::FloorToDouble(Budget)||Budget<1||Budget>32){Check(false,TEXT("feedback profile valid"));Finish();return;}
 for(const auto& Pair:(*Specs)->Values){const auto Spec=Pair.Value->AsObject();FOAGDFeedbackCue Cue;FString Domain,Overflow,Audio,Visual;double Duration=0,Volume=0,CameraAmount=0,Limit=0;const TArray<TSharedPtr<FJsonValue>>* Color=nullptr;
  if(!Spec.IsValid()||!Spec->TryGetStringField(TEXT("domain"),Domain)||(Domain!=TEXT("game")&&Domain!=TEXT("ui"))||!Spec->TryGetStringField(TEXT("overflow"),Overflow)||(Overflow!=TEXT("reject")&&Overflow!=TEXT("oldest"))||!Spec->TryGetBoolField(TEXT("loop"),Cue.Loop)||!Spec->TryGetBoolField(TEXT("spatial"),Cue.Spatial)||!Spec->TryGetNumberField(TEXT("duration"),Duration)||!Spec->TryGetNumberField(TEXT("volume"),Volume)||!Spec->TryGetNumberField(TEXT("camera"),CameraAmount)||!Spec->TryGetNumberField(TEXT("limit"),Limit)||Limit!=FMath::FloorToDouble(Limit)||Limit<1||Limit>16||!Spec->TryGetStringField(TEXT("audio"),Audio)||!Spec->TryGetStringField(TEXT("visual"),Visual)||!Spec->TryGetArrayField(TEXT("color"),Color)||Color->Num()!=3){Check(false,TEXT("cue fields valid"));Finish();return;}
  Cue.UI=Domain==TEXT("ui");Cue.ReplaceOldest=Overflow==TEXT("oldest");Cue.Duration=Duration;Cue.Volume=Volume;Cue.Camera=CameraAmount;Cue.Limit=int32(Limit);double Channels[3];for(int32 I=0;I<3;++I){if(!(*Color)[I]->TryGetNumber(Channels[I])){Check(false,TEXT("cue tint numeric"));Finish();return;}}Cue.Color=FLinearColor(Channels[0],Channels[1],Channels[2],1);
  if(!Audio.IsEmpty()){Cue.Sound=LoadObject<USoundWave>(nullptr,*(TEXT("/Game/Feedback/")+Audio+TEXT(".")+Audio));if(!Cue.Sound){Check(false,TEXT("imported audio binding exists"));Finish();return;}}
  if(Visual==TEXT("pulse"))Cue.Visual=AFeedbackRing::StaticClass();else if(!Visual.IsEmpty()){Check(false,TEXT("visual binding exists"));Finish();return;}
  const FName Name(*Pair.Key);if(Bindings.Contains(Name)){Check(false,TEXT("cue identifiers unique"));Finish();return;}Bindings.Add(Name,Cue);
 }
 if(!Feedback->Configure(Bindings,int32(Budget),Error)){Check(false,Error);Finish();return;}
 Feedback->Lifecycle.AddDynamic(this,&AStateController::OnFeedback);PhaseStart=FPlatformTime::Seconds();
}
FString AStateController::EventId(const FString& Kind){return Kind+FString::Printf(TEXT(":%d"),++EventSerial);}
void AStateController::OnFeedback(int32 Handle,FString Event,FName Cue,FString Status){if(Status==TEXT("started"))++StartCount;else ++EndCount;if(Events.Num()>=10000)return;auto Item=MakeShared<FJsonObject>();Item->SetNumberField(TEXT("t_seconds"),FPlatformTime::Seconds()-StartedAt);Item->SetNumberField(TEXT("handle"),Handle);Item->SetStringField(TEXT("event"),Event);Item->SetStringField(TEXT("cue"),Cue.ToString());Item->SetStringField(TEXT("state"),Status);Events.Add(MakeShared<FJsonValueObject>(Item));if(CallbackTest&&Status==TEXT("scope-ended")){CallbackTest=false;FString Error;const auto Config=Feedback->Cues;CallbackRejected=Feedback->Play(TEXT("ui"),TEXT("nested"),nullptr,FVector::ZeroVector,false,TEXT("ui"))==-1&&!Feedback->Configure(Config,8,Error);Feedback->Clear();}}
void AStateController::CheckZone(){if(!GetPawn()||Busy||Router->IsPaused()||!Scenes->Current)return;const FVector At=GetPawn()->GetActorLocation();const bool Inside=FVector2D(At.X-500,At.Y).Size()<150;if(Inside&&!ZoneInside)ZoneHandle=Feedback->Play(TEXT("zone"),EventId(TEXT("zone")),Door(Scenes->Current,State->GetStringField(TEXT("scene"))),FVector(100,0,-140),true,TEXT("scene"));else if(!Inside&&ZoneInside){Feedback->Stop(ZoneHandle,TEXT("zone-exit"));ZoneHandle=-1;}ZoneInside=Inside;}
void AStateController::TestStep(){
 if(FPlatformTime::Seconds()-PhaseStart<.12)return;auto* PawnActor=Cast<AStatePlayer>(GetPawn());if(!PawnActor)return;FString Error;
 if(Phase==0){
  UAudioMixerBlueprintLibrary::StartRecordingOutput(this,15);Check(Feedback->Cues.Num()==4,TEXT("four event families resolve native resources"));auto Bad=Feedback->Cues;Bad[TEXT("door")].Volume=2;Check(!Feedback->Configure(Bad,8,Error)&&Feedback->Cues.Num()==4,TEXT("bad cue rejected without replacing working profile"));Bad=Feedback->Cues;Bad[TEXT("zone")].Loop=false;Check(!Feedback->Configure(Bad,8,Error),TEXT("loop resource mismatch rejected"));CloseMenu();Choose(1);for(const auto& Pair:Feedback->Active)TestHandle=Pair.Key;Check(State->GetObjectField(TEXT("objects"))->GetBoolField(TEXT("door-a"))&&Feedback->Active.Contains(TestHandle),TEXT("committed door state emits mapped feedback"));Next();
 }else if(Phase==1){
  auto* Item=Feedback->Active.Find(TestHandle);Check(Item&&Item->Audio&&Item->Audio->IsPlaying()&&Item->Visual&&!Item->Visual->IsHidden(),TEXT("real audio player and rendered effect active"));Check(PeakCamera>.001,TEXT("camera contribution reaches actual camera"));FScreenshotRequest::RequestScreenshot(Report+TEXT("-peak.png"),false,false);OpenMenu();FrozenAge=Item?Item->Age:-1;Check(Item&&Item->Audio->GetPlayState()==EAudioComponentPlayState::Paused,TEXT("pause suspends native game audio"));Check(Feedback->Play(TEXT("action"),EventId(TEXT("paused")),PawnActor,FVector::ZeroVector,false,TEXT("scene"))==-1,TEXT("game feedback rejected during pause"));TestUI=Feedback->Play(TEXT("ui"),EventId(TEXT("ui")),nullptr,FVector::ZeroVector,false,TEXT("ui"));Check(TestUI>0&&Feedback->Active[TestUI].Audio->GetPlayState()!=EAudioComponentPlayState::Paused,TEXT("UI audio continues while game paused"));Next();
 }else if(Phase==2&&Frame>2&&FPlatformTime::Seconds()-PhaseStart>.45){
  auto* Item=Feedback->Active.Find(TestHandle);Check(Item&&FMath::IsNearlyEqual(Item->Age,FrozenAge,.001f),TEXT("game visual and camera clock frozen during pause"));Check(!Feedback->Active.Contains(TestUI),TEXT("UI feedback expires on real-time clock while paused"));CloseMenu();Next();
 }else if(Phase==3&&FPlatformTime::Seconds()-PhaseStart>.7){
  Check(Feedback->Active.IsEmpty()&&Feedback->CameraOffset.IsNearlyZero(),TEXT("one-shot finishes and camera returns without drift"));const FString Duplicate=EventId(TEXT("duplicate"));const int32 First=Feedback->Play(TEXT("door"),Duplicate,nullptr,FVector::ZeroVector,false,TEXT("scene"));Check(Feedback->Play(TEXT("door"),Duplicate,nullptr,FVector::ZeroVector,false,TEXT("scene"))==-1&&Feedback->Active.Num()==1,TEXT("same event not played twice"));const int32 Second=Feedback->Play(TEXT("door"),EventId(TEXT("door")),nullptr,FVector::ZeroVector,false,TEXT("scene"));const int32 Third=Feedback->Play(TEXT("door"),EventId(TEXT("door")),nullptr,FVector::ZeroVector,false,TEXT("scene"));Check(!Feedback->Active.Contains(First)&&Feedback->Active.Contains(Second)&&Feedback->Active.Contains(Third),TEXT("per-cue budget replaces oldest deterministically"));const auto Valid=Feedback->Cues;Check(!Feedback->Configure(Valid,8,Error),TEXT("live reconfiguration rejected"));Check(Feedback->Stop(Second)&&!Feedback->Stop(Second),TEXT("stop handle is idempotent"));Check(Feedback->Play(TEXT("door"),Duplicate,nullptr,FVector::ZeroVector,false,TEXT("scene"))==-1,TEXT("event deduplication survives instance completion"));Check(Feedback->Play(TEXT("action"),EventId(TEXT("invalid")),nullptr,FVector::ZeroVector,false,TEXT("scene"),std::numeric_limits<float>::quiet_NaN())==-1,TEXT("nonfinite strength rejected"));Feedback->Clear();Feedback->Configure(Valid,1,Error);Feedback->Play(TEXT("door"),EventId(TEXT("budget")),nullptr,FVector::ZeroVector,false,TEXT("scene"));Check(Feedback->Play(TEXT("action"),EventId(TEXT("budget")),nullptr,FVector::ZeroVector,false,TEXT("scene"))==-1&&Feedback->Active.Num()==1,TEXT("global budget rejects excess across cues"));Feedback->Clear();Feedback->Configure(Valid,8,Error);Check(Feedback->Play(TEXT("zone"),EventId(TEXT("orphan")),nullptr,FVector::ZeroVector,false,TEXT("scene"))==-1,TEXT("loop cannot start without owner"));auto* OwnerActor=GetWorld()->SpawnActor<AStaticMeshActor>();OwnerActor->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);TestOwner=OwnerActor;TestHandle=Feedback->Play(TEXT("zone"),EventId(TEXT("zone")),TestOwner,FVector(100,0,0),true,TEXT("scene"));Check(Feedback->Play(TEXT("zone"),EventId(TEXT("zone")),TestOwner,FVector::ZeroVector,false,TEXT("scene"))==-1,TEXT("loop concurrency rejects repeat owner emission"));TestOwner->SetActorLocation(FVector(200,0,0));Next();
 }else if(Phase==4&&FPlatformTime::Seconds()-PhaseStart>1.2){
  auto* Item=Feedback->Active.Find(TestHandle);Check(Item&&Item->Visual&&Item->Audio&&Item->Visual->GetActorLocation().Equals(FVector(300,0,0),.01)&&Item->Audio->GetComponentLocation().Equals(FVector(300,0,0),.01),TEXT("visual and 3D audio follow live attachment"));Check(Item&&Item->Audio&&Item->Audio->IsPlaying()&&Item->Age>1.f,TEXT("native loop continues beyond source clip duration"));Independent=Feedback->Play(TEXT("action"),EventId(TEXT("world")),nullptr,FVector::ZeroVector,false,TEXT("scene"));TestOwner->Destroy();Next();
 }else if(Phase==5){Check(!Feedback->Active.Contains(TestHandle)&&Feedback->Active.Contains(Independent),TEXT("owner destruction stops its loop but preserves independent effect"));Feedback->Clear();Choose(6);Next();}
 else if(Phase==6&&FPlatformTime::Seconds()-PhaseStart>.2){Check(ZoneInside&&ZoneHandle>0&&Feedback->Active.Contains(ZoneHandle),TEXT("actual player position enters zone and starts loop"));FScreenshotRequest::RequestScreenshot(Report+TEXT("-zone.png"),true,false);Choose(6);Next();}
 else if(Phase==7){Check(!ZoneInside&&ZoneHandle==-1&&Feedback->Active.IsEmpty(),TEXT("leaving zone stops native loop and visual"));Choose(5);Next();}
 else if(Phase==8){Check(Feedback->Active.Num()==1,TEXT("action event uses same independent feedback interface"));const int32 Retained=Feedback->Play(TEXT("ui"),EventId(TEXT("global")),nullptr,FVector::ZeroVector,false,TEXT("ui"));Feedback->StopScope(TEXT("scene"));Check(Feedback->Active.Num()==1&&Feedback->Active.Contains(Retained),TEXT("scene scope cleanup preserves unrelated UI feedback"));Feedback->Clear();Choose(6);Next();}
 else if(Phase==9){Feedback->Clear();Feedback->Play(TEXT("door"),EventId(TEXT("callback")),nullptr,FVector::ZeroVector,false,TEXT("scene"));Feedback->Play(TEXT("action"),EventId(TEXT("callback")),nullptr,FVector::ZeroVector,false,TEXT("scene"));CallbackTest=true;Feedback->StopScope(TEXT("scene"));Check(CallbackRejected&&Feedback->Active.IsEmpty(),TEXT("callback cleanup is safe and nested play/configure rejected"));ZoneInside=false;PawnActor->ResetMotor(FVector(500,0,100));Phase=12;Next();}
 else if(Phase==13){Choose(2);Phase=9;Next();}
 else if(Phase==10){bool NoScene=true;for(const auto& Pair:Feedback->Active)if(Pair.Value.Scope==TEXT("scene"))NoScene=false;Check(State->GetStringField(TEXT("scene"))==TEXT("b")&&NoScene,TEXT("real scene replacement clears old feedback"));Feedback->Clear();Next();}
 else if(Phase==11){Check(PreviousCamera.IsNearlyZero(.001)&&Feedback->Active.IsEmpty(),TEXT("clear removes instances and camera contribution"));Check(StartCount==EndCount,TEXT("every started instance has a terminal lifecycle record"));UAudioMixerBlueprintLibrary::StopRecordingOutput(this,EAudioRecordingExportType::WavFile,FPaths::GetCleanFilename(Report),FPaths::GetPath(Report));OpenMenu();FScreenshotRequest::RequestScreenshot(Report+TEXT("-clear.png"),true,false);Next();}
 else if(Phase==12&&FPlatformTime::Seconds()-PhaseStart>.5){Check(IFileManager::Get().FileSize(*(Report+TEXT(".wav")))>4096,TEXT("native mixer output captured as playable WAV"));Finish();}
}
