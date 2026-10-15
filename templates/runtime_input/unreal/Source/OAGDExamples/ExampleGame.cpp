#include "ExampleGame.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/GameViewportClient.h"
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

class SInputMenuRoot : public SCompoundWidget {
public:
 SLATE_BEGIN_ARGS(SInputMenuRoot){} SLATE_ARGUMENT(TWeakObjectPtr<AInputController>,Controller) SLATE_DEFAULT_SLOT(FArguments,Content) SLATE_END_ARGS()
 void Construct(const FArguments& Args){Controller=Args._Controller;ChildSlot[Args._Content.Widget];}
 virtual FReply OnPreviewKeyDown(const FGeometry&,const FKeyEvent& Event)override{return Forward(Event,true);}
 virtual FReply OnKeyUp(const FGeometry&,const FKeyEvent& Event)override{return Forward(Event,false);}
 virtual FReply OnAnalogValueChanged(const FGeometry&,const FAnalogInputEvent& Event)override{
  if(Controller.IsValid()){FInputKeyEventArgs Args(nullptr,Event.GetInputDeviceId(),Event.GetKey(),Event.GetAnalogValue(),1.f/60.f,1,FPlatformTime::Cycles64());if(Controller->InputKey(Args))return FReply::Handled();}return FReply::Unhandled();
 }
private:
 TWeakObjectPtr<AInputController> Controller;
 FReply Forward(const FKeyEvent& Event,bool Down){if(Controller.IsValid()){
  // Same native key structure as viewport input; the UI forwards events consumed
  // by its focus path. Simulated flag is not used for physical-event claims.
  FInputKeyEventArgs Args(nullptr,Event.GetInputDeviceId(),Event.GetKey(),Down?(Event.IsRepeat()?IE_Repeat:IE_Pressed):IE_Released,FPlatformTime::Cycles64());
  if(Controller->InputKey(Args))return FReply::Handled();
 }return FReply::Unhandled();}
};
AInputPlayer::AInputPlayer(){
 auto* Visual=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));Visual->SetupAttachment(RootComponent);
 static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeAsset(TEXT("/Engine/BasicShapes/Cube.Cube"));Visual->SetStaticMesh(CubeAsset.Object);Visual->SetRelativeScale3D(FVector(.6,.6,1.6));Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
 PrimaryActorTick.bCanEverTick=true;
}
void AInputPlayer::Tick(float Delta){Super::Tick(Delta);if(auto* PC=Cast<AInputController>(Controller)){MoveWorld(FVector2D(PC->Router->Strength(TEXT("forward"))-PC->Router->Strength(TEXT("back")),PC->Router->Strength(TEXT("right"))-PC->Router->Strength(TEXT("left"))));}}
AExampleGame::AExampleGame(){DefaultPawnClass=AInputPlayer::StaticClass();PlayerControllerClass=AInputController::StaticClass();}
void AExampleGame::BeginPlay(){
 Super::BeginPlay();auto* Floor=GetWorld()->SpawnActor<AStaticMeshActor>(FVector(0,0,-50),FRotator::ZeroRotator);Floor->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));Floor->SetActorScale3D(FVector(30,30,1));Floor->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
 auto* Light=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,500),FRotator(-55,-30,0));Light->GetLightComponent()->SetMobility(EComponentMobility::Movable);Light->GetLightComponent()->SetIntensity(5.f);
}
AInputController::AInputController(){Router=CreateDefaultSubobject<UOAGDInputComponent>(TEXT("InputRouter"));PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.bTickEvenWhenPaused=true;bShouldPerformFullTickWhenPaused=true;}
void AInputController::BeginPlay(){
 Super::BeginPlay();Testing=FParse::Param(FCommandLine::Get(),TEXT("OAGDSelfTest"));Report=FPaths::ProjectSavedDir()/TEXT("input-validation.json");FParse::Value(FCommandLine::Get(),TEXT("InputReport="),Report);Preference=Testing?TEXT("input-test.json"):TEXT("input-preferences.json");
 FString Error;if(!Router->LoadProfile(FPaths::ProjectContentDir()/TEXT("OAGDData/input-profile.json"),Error)){Message=Error;Check(false,Error);Finish();return;}
 if(!Testing&&FPaths::FileExists(FPaths::ProjectSavedDir()/TEXT("OAGDInput")/Preference))Router->LoadPreferences(Preference,Message);
 Router->ActionChanged.AddDynamic(this,&AInputController::OnAction);Router->PauseChanged.AddDynamic(this,&AInputController::OnPause);Router->CaptureFinished.AddDynamic(this,&AInputController::OnCapture);
 if(auto* PawnActor=Cast<AInputPlayer>(GetPawn()))PawnActor->ResetMotor(FVector(0,0,100));
 bShowMouseCursor=true;BuildUI();OpenMenu();
}
void AInputController::EndPlay(const EEndPlayReason::Type Reason){if(UI.IsValid()&&GetWorld()->GetGameViewport())GetWorld()->GetGameViewport()->RemoveViewportWidgetContent(UI.ToSharedRef());Focus.Clear();Super::EndPlay(Reason);}
bool AInputController::InputKey(const FInputKeyEventArgs& Args){if(Router&&Router->HandleInput(Args))return true;return Super::InputKey(Args);}
void AInputController::OnPause(bool Paused){if(auto* PawnActor=Cast<AInputPlayer>(GetPawn())){PawnActor->ConsumeMovementInputVector();if(Paused)PawnActor->GetCharacterMovement()->StopMovementImmediately();}SetPause(Paused);}
void AInputController::OpenMenu(){Router->SetContext(TEXT("ui"));Router->SetPause(TEXT("menu"),true);MenuOpen=true;Menu->SetVisibility(EVisibility::Visible);Selection=0;FInputModeGameAndUI Mode;Mode.SetWidgetToFocus(Buttons[0]);Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);Mode.SetHideCursorDuringCapture(false);SetInputMode(Mode);Focus.Push(Buttons[0].ToSharedRef());bShowMouseCursor=true;}
void AInputController::CloseMenu(){Started=true;Router->CancelCapture();MenuOpen=false;Menu->SetVisibility(EVisibility::Collapsed);Focus.Pop();Router->SetContext(TEXT("game"));Router->SetPause(TEXT("menu"),false);FInputModeGameOnly Mode;SetInputMode(Mode);bShowMouseCursor=false;}
void AInputController::Select(int32 Index){Selection=(Index+Buttons.Num())%Buttons.Num();if(FSlateApplication::IsInitialized())FSlateApplication::Get().SetKeyboardFocus(Buttons[Selection],EFocusCause::SetDirectly);}
void AInputController::Choose(int32 Index){
 if(Index==0)CloseMenu();else if(Index==7){Router->RestoreDefaults();Router->SavePreferences(Preference,Message);}else if(Index==8)UKismetSystemLibrary::QuitGame(this,this,EQuitPreference::Quit,false);
 else{static const FName Names[]={TEXT("forward"),TEXT("back"),TEXT("left"),TEXT("right"),TEXT("act"),TEXT("act")};if(Router->BeginCapture(Names[Index-1],Index==6?1:0))Message=TEXT("Press a new key / button; Escape cancels");}
}
void AInputController::OnAction(FName Action,float Value){if(Value<.5f)return;
 if(MenuOpen&&FSlateApplication::IsInitialized()){auto Current=FSlateApplication::Get().GetKeyboardFocusedWidget();for(int32 I=0;I<Buttons.Num();++I)if(Current==Buttons[I])Selection=I;}
 if(Action==TEXT("pause")){if(MenuOpen&&Started)CloseMenu();else if(!MenuOpen)OpenMenu();}
 else if(Action==TEXT("act"))++Actions;
 else if(Action==TEXT("ui_up"))Select(Selection-1);else if(Action==TEXT("ui_down"))Select(Selection+1);
 else if(Action==TEXT("ui_accept"))Choose(Selection);else if(Action==TEXT("ui_back")&&Started)CloseMenu();
}
void AInputController::OnCapture(bool Success,FString Detail){Message=(Success?TEXT("Bound: "):TEXT("Not changed: "))+Detail;if(Success){FString Error;if(!Router->SavePreferences(Preference,Error))Message=Error;}}
void AInputController::BuildUI(){
 auto Column=SNew(SVerticalBox);
 Column->AddSlot().AutoHeight().Padding(20)[SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Bold",20)).Text_Lambda([this]{return FText::FromString(FString::Printf(TEXT("OAGD Input | UE 5.8 | Actions: %d\nMove: WASD / left stick | Act: Space / South | Menu: Esc / Start\nMenu: arrows / D-pad, Enter / South\n%s"),Actions,*Message));})];
 SAssignNew(Menu,SVerticalBox);
 Menu->AddSlot().AutoHeight().Padding(8)[SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Bold",24)).Text_Lambda([this]{return FText::FromString(Started?TEXT("PAUSED / INPUT SETTINGS"):TEXT("INPUT & PAUSE EXAMPLE"));})];
 for(int32 I=0;I<9;++I){TSharedPtr<SButton> Button;
  Menu->AddSlot().AutoHeight().Padding(6)[SAssignNew(Button,SButton).ContentPadding(FMargin(15,8)).OnClicked_Lambda([this,I]{Selection=I;Choose(I);return FReply::Handled();})[
   SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Regular",18)).Text_Lambda([this,I]{
    if(I==0)return FText::FromString(Started?TEXT("Resume"):TEXT("Start"));if(I==7)return FText::FromString(TEXT("Restore defaults"));if(I==8)return FText::FromString(TEXT("Quit"));
    static const FName Names[]={TEXT("forward"),TEXT("back"),TEXT("left"),TEXT("right"),TEXT("act"),TEXT("act")};return FText::FromString(TEXT("Rebind ")+FString(I==6?TEXT("gamepad action"):*Names[I-1].ToString())+TEXT(": ")+Router->Binding(Names[I-1],I==6?1:0));})]];Buttons.Add(Button);
 }
 Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(15)[SNew(SBox).WidthOverride(520)[SNew(SBorder).Padding(16)[Menu.ToSharedRef()]]];
 UI=SNew(SInputMenuRoot).Controller(this)[Column];GetWorld()->GetGameViewport()->AddViewportWidgetContent(UI.ToSharedRef(),10);
}
void AInputController::Key(FKey Value,bool Down){InputKey(FInputKeyEventArgs::CreateSimulated(Value,Down?IE_Pressed:IE_Released,Down?1.f:0.f));}
void AInputController::Pad(float Value){InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::Gamepad_LeftX,IE_Axis,Value,1,FInputDeviceId::CreateFromInternalId(7)));}
void AInputController::Check(bool Ok,const FString& Name){Checks.Add(Name);if(!Ok)Failures.Add(Name);}
void AInputController::Tick(float Delta){Super::Tick(Delta);if(Testing&&!Finished){++Frame;TestStep();}}
void AInputController::TestStep(){
 auto* PawnActor=Cast<AInputPlayer>(GetPawn());if(!PawnActor||Frame<8)return;FString Error;
 if(Phase==0){auto UIKey=[](FKey K,bool Down){FKeyEvent E(K,FModifierKeysState(),0,false,0,0);if(Down)FSlateApplication::Get().ProcessKeyDownEvent(E);else FSlateApplication::Get().ProcessKeyUpEvent(E);};Check(MenuOpen&&UGameplayStatics::IsGamePaused(this),TEXT("start menu owns paused world"));UIKey(EKeys::Down,true);UIKey(EKeys::Down,false);Check(Selection==1,TEXT("Slate focus routing navigates UI while paused"));UIKey(EKeys::Up,true);UIKey(EKeys::Up,false);UIKey(EKeys::Enter,true);UIKey(EKeys::Enter,false);Check(Started&&!UGameplayStatics::IsGamePaused(this),TEXT("native input starts game and restores world"));Next();}
 else if(Phase==1){Before=PawnActor->GetActorLocation();Key(EKeys::D,true);Next();}
 else if(Phase==2&&Frame>=30){Check(PawnActor->GetActorLocation().Y>Before.Y+30,TEXT("native InputKey moves real CharacterMovement"));Key(EKeys::Escape,true);Key(EKeys::Escape,false);Before=PawnActor->GetActorLocation();Next();}
 else if(Phase==3&&Frame>=15){Check(PawnActor->GetActorLocation().Equals(Before,.01)&&Router->Strength(TEXT("right"))==0,TEXT("pause freezes physics and suppresses held movement"));Key(EKeys::Enter,true);Key(EKeys::Enter,false);Check(Router->Strength(TEXT("right"))==0,TEXT("held key does not leak across resume"));Key(EKeys::D,false);Key(EKeys::D,true);Check(Router->Strength(TEXT("right"))==1,TEXT("release and repress re-arms movement"));Key(EKeys::D,false);Count=Actions;Key(EKeys::SpaceBar,true);Key(EKeys::SpaceBar,false);Check(Actions==Count+1,TEXT("project callback receives game action"));OpenMenu();Key(EKeys::SpaceBar,true);Key(EKeys::SpaceBar,false);Check(Actions==Count+1,TEXT("menu input cannot trigger gameplay"));Router->SetPause(TEXT("dialog"),true);CloseMenu();Check(UGameplayStatics::IsGamePaused(this),TEXT("closing menu preserves another pause owner"));Router->SetPause(TEXT("dialog"),false);Check(!UGameplayStatics::IsGamePaused(this),TEXT("last pause owner releases world"));Next();}
 else if(Phase==4){Check(!Router->Rebind(TEXT("act"),0,TEXT("W"),Error)&&Router->Binding(TEXT("act"))==TEXT("Space"),TEXT("same-context conflict rejected without mutation"));Check(!Router->Rebind(TEXT("act"),0,TEXT("Escape"),Error),TEXT("global binding conflict rejected"));OpenMenu();Choose(5);Key(EKeys::F,true);Key(EKeys::F,false);Check(Router->Binding(TEXT("act"))==TEXT("F")&&Message.StartsWith(TEXT("Bound")),TEXT("native capture updates binding and preferences"));CloseMenu();Count=Actions;Key(EKeys::SpaceBar,true);Key(EKeys::SpaceBar,false);Key(EKeys::F,true);Key(EKeys::F,false);Check(Actions==Count+1,TEXT("old key stops and new key invokes game action"));Router->RestoreDefaults();Check(Router->Binding(TEXT("act"))==TEXT("Space"),TEXT("defaults restored"));Check(Router->LoadPreferences(Preference,Error)&&Router->Binding(TEXT("act"))==TEXT("F"),TEXT("preferences reload into actual consumer"));OpenMenu();Choose(5);Key(EKeys::Escape,true);Key(EKeys::Escape,false);Check(MenuOpen&&Router->Binding(TEXT("act"))==TEXT("F"),TEXT("capture cancellation does not close menu or mutate binding"));CloseMenu();Next();}
 else if(Phase==5){Pad(.1f);Check(Router->Strength(TEXT("right"))==0,TEXT("analog deadzone suppresses drift"));Pad(.6f);Check(FMath::IsNearlyEqual(Router->Strength(TEXT("right")),.5f,.001f),TEXT("gamepad axis rescaled beyond deadzone"));Router->DisconnectPad(7);Check(Router->Strength(TEXT("right"))==0&&Router->SelectedPad==-1,TEXT("device disconnect releases active axis"));Pad(.8f);Check(Router->Strength(TEXT("right"))>.7f,TEXT("reconnected device can produce new input"));Pad(0);Key(EKeys::W,true);Router->FocusLost();Check(Router->Strength(TEXT("forward"))==0,TEXT("window focus loss releases active input"));Key(EKeys::W,false);FFileHelper::SaveStringToFile(TEXT("{bad-json"),*(FPaths::ProjectSavedDir()/TEXT("OAGDInput/invalid-input-test.json")));Check(!Router->LoadPreferences(TEXT("invalid-input-test.json"),Error)&&Router->Binding(TEXT("act"))==TEXT("F"),TEXT("invalid preferences preserve active configuration"));OpenMenu();Select(0);Focus.Push(Buttons[5].ToSharedRef());Focus.Pop();Check(FSlateApplication::Get().GetKeyboardFocusedWidget()==Buttons[0],TEXT("nested focus scope restores previous live control"));if(!FParse::Param(FCommandLine::Get(),TEXT("nullrhi")))FScreenshotRequest::RequestScreenshot(Report+TEXT(".png"),true,false);Next();}
 else if(Phase==6)Finish();
}
void AInputController::Finish(){
 Finished=true;auto Root=MakeShared<FJsonObject>();Root->SetStringField(TEXT("engine"),FEngineVersion::Current().ToString());Root->SetBoolField(TEXT("no_animation_plugin"),true);Root->SetStringField(TEXT("input"),TEXT("Native PlayerController InputKey dispatch; disconnect/focus hooks simulated; no physical device or human claim"));TArray<TSharedPtr<FJsonValue>> C,F;for(const auto& S:Checks)C.Add(MakeShared<FJsonValueString>(S));for(const auto& S:Failures)F.Add(MakeShared<FJsonValueString>(S));Root->SetArrayField(TEXT("checks"),C);Root->SetArrayField(TEXT("failures"),F);FString Text;FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*Report,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);FPlatformMisc::RequestExitWithStatus(false,Failures.Num()?1:0);
}
