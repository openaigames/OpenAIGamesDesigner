#include "OAGDInput.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CoreDelegates.h"
#include "HAL/FileManager.h"
#include "GenericPlatform/GenericPlatformInputDeviceMapper.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "UnrealClient.h"

namespace {
const TMap<FString,FString> KeyTokens={
 {TEXT("SpaceBar"),TEXT("Space")},{TEXT("Escape"),TEXT("Escape")},{TEXT("Enter"),TEXT("Enter")},
 {TEXT("Tab"),TEXT("Tab")},{TEXT("BackSpace"),TEXT("Backspace")},{TEXT("Up"),TEXT("Up")},{TEXT("Down"),TEXT("Down")},{TEXT("Left"),TEXT("Left")},{TEXT("Right"),TEXT("Right")},
 {TEXT("LeftMouseButton"),TEXT("MouseLeft")},{TEXT("RightMouseButton"),TEXT("MouseRight")},{TEXT("MiddleMouseButton"),TEXT("MouseMiddle")},
 {TEXT("LeftShift"),TEXT("Shift")},{TEXT("RightShift"),TEXT("Shift")},{TEXT("LeftControl"),TEXT("Ctrl")},{TEXT("RightControl"),TEXT("Ctrl")},{TEXT("LeftAlt"),TEXT("Alt")},{TEXT("RightAlt"),TEXT("Alt")},
 {TEXT("MouseScrollUp"),TEXT("MouseWheelUp")},{TEXT("MouseScrollDown"),TEXT("MouseWheelDown")},
 {TEXT("Gamepad_FaceButton_Bottom"),TEXT("PadSouth")},{TEXT("Gamepad_FaceButton_Right"),TEXT("PadEast")},{TEXT("Gamepad_FaceButton_Left"),TEXT("PadWest")},{TEXT("Gamepad_FaceButton_Top"),TEXT("PadNorth")},
 {TEXT("Gamepad_Special_Right"),TEXT("PadStart")},{TEXT("Gamepad_Special_Left"),TEXT("PadBack")},
 {TEXT("Gamepad_LeftShoulder"),TEXT("PadL1")},{TEXT("Gamepad_RightShoulder"),TEXT("PadR1")},
 {TEXT("Gamepad_DPad_Up"),TEXT("PadUp")},{TEXT("Gamepad_DPad_Down"),TEXT("PadDown")},{TEXT("Gamepad_DPad_Left"),TEXT("PadLeft")},{TEXT("Gamepad_DPad_Right"),TEXT("PadRight")},
 {TEXT("Zero"),TEXT("0")},{TEXT("One"),TEXT("1")},{TEXT("Two"),TEXT("2")},{TEXT("Three"),TEXT("3")},{TEXT("Four"),TEXT("4")},{TEXT("Five"),TEXT("5")},{TEXT("Six"),TEXT("6")},{TEXT("Seven"),TEXT("7")},{TEXT("Eight"),TEXT("8")},{TEXT("Nine"),TEXT("9")}};
}
UOAGDInputComponent::UOAGDInputComponent(){PrimaryComponentTick.bCanEverTick=true;PrimaryComponentTick.bTickEvenWhenPaused=true;}
void UOAGDInputComponent::BeginPlay(){
 Super::BeginPlay();
 ConnectionHandle=IPlatformInputDeviceMapper::Get().GetOnInputDeviceConnectionChange().AddWeakLambda(this,[this](EInputDeviceConnectionState State,FPlatformUserId,FInputDeviceId Device){if(State==EInputDeviceConnectionState::Disconnected)DisconnectPad(Device.GetId());});
 DeactivateHandle=FCoreDelegates::ApplicationWillDeactivateDelegate.AddUObject(this,&UOAGDInputComponent::FocusLost);
}
void UOAGDInputComponent::EndPlay(const EEndPlayReason::Type Reason){
 IPlatformInputDeviceMapper::Get().GetOnInputDeviceConnectionChange().Remove(ConnectionHandle);
 FCoreDelegates::ApplicationWillDeactivateDelegate.Remove(DeactivateHandle);
 FocusLost();Pauses.Reset();Super::EndPlay(Reason);
}
void UOAGDInputComponent::TickComponent(float Delta,ELevelTick Tick,FActorComponentTickFunction* Function){
 Super::TickComponent(Delta,Tick,Function);
 if(auto* Client=GetWorld()->GetGameViewport()){if(Client->Viewport){bool Focus=Client->Viewport->HasFocus();if(HadFocus&&!Focus)FocusLost();HadFocus=Focus;}}
}
bool UOAGDInputComponent::Supported(const FString& Key){
 if(Key.Len()==1&&((Key[0]>='A'&&Key[0]<='Z')||(Key[0]>='0'&&Key[0]<='9')))return true;
 for(const auto& Pair:KeyTokens)if(Pair.Value==Key)return true;
 return Key==TEXT("PadLeftX+")||Key==TEXT("PadLeftX-")||Key==TEXT("PadLeftY+")||Key==TEXT("PadLeftY-");
}
FString UOAGDInputComponent::Token(FKey Key){FString Name=Key.ToString();if(const auto* Value=KeyTokens.Find(Name))return *Value;return Supported(Name)?Name:FString();}
bool UOAGDInputComponent::Validate(const TMap<FName,FOAGDInputBinding>& Data,FString& Error){
 if(Data.IsEmpty()||Data.Num()>128){Error=TEXT("Invalid actions");return false;}
 TMap<FString,TArray<FName>> Used;
 for(const auto& Pair:Data){const auto& Row=Pair.Value;
  if(Pair.Key.IsNone()||(Row.Context!=TEXT("game")&&Row.Context!=TEXT("ui")&&Row.Context!=TEXT("global"))||Row.Keys.Num()<1||Row.Keys.Num()>8){Error=TEXT("Invalid action contract");return false;}
  for(const auto& Key:Row.Keys){if(!Supported(Key)){Error=TEXT("Unsupported key: ")+Key;return false;}
   for(FName Other:Used.FindOrAdd(Key)){const auto& ContextValue=Data[Other].Context;if(ContextValue==Row.Context||ContextValue==TEXT("global")||Row.Context==TEXT("global")){Error=TEXT("Binding conflict: ")+Key+TEXT(" (")+Other.ToString()+TEXT(", ")+Pair.Key.ToString()+TEXT(")");return false;}}
   Used.FindOrAdd(Key).Add(Pair.Key);
  }
 }return true;
}
bool UOAGDInputComponent::Parse(const FString& Text,FString& Id,float& Zone,TMap<FName,FOAGDInputBinding>& Out,FString& Error){
 TSharedPtr<FJsonObject> Root;FString Schema;double D=0;const TSharedPtr<FJsonObject>* Rows=nullptr;
 if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)||!Root.IsValid()||!Root->TryGetStringField(TEXT("schema"),Schema)||Schema!=TEXT("oagd.input/1")||!Root->TryGetStringField(TEXT("id"),Id)||Id.IsEmpty()||!Root->TryGetNumberField(TEXT("deadzone"),D)||!FMath::IsFinite(D)||D<.05||D>.8||!Root->TryGetObjectField(TEXT("actions"),Rows)){Error=TEXT("Invalid input profile");return false;}
 if(!Rows){Error=TEXT("Missing actions");return false;}Zone=D;Out.Reset();
 for(const auto& Pair:(*Rows)->Values){const auto Row=Pair.Value->AsObject();FOAGDInputBinding B;const TArray<TSharedPtr<FJsonValue>>* Keys;
  if(!Row.IsValid()||!Row->TryGetStringField(TEXT("context"),B.Context)||!Row->TryGetBoolField(TEXT("rebindable"),B.Rebindable)||!Row->TryGetArrayField(TEXT("keys"),Keys)||Out.Contains(FName(*Pair.Key))){Error=TEXT("Invalid or duplicate action");return false;}
  for(const auto& Key:*Keys){FString Name;if(!Key->TryGetString(Name)){Error=TEXT("Invalid key");return false;}B.Keys.Add(Name);}Out.Add(FName(*Pair.Key),B);
 }return Validate(Out,Error);
}
bool UOAGDInputComponent::LoadProfile(const FString& Path,FString& Error){FString Text;if(!FFileHelper::LoadFileToString(Text,*Path)){Error=TEXT("Cannot read input profile");return false;}return Configure(Text,Error);}
bool UOAGDInputComponent::Configure(const FString& Json,FString& Error){
 TMap<FName,FOAGDInputBinding> New;float Zone;FString Id;if(!Parse(Json,Id,Zone,New,Error))return false;
 FocusLost();Actions=New;Defaults=New;ProfileId=Id;Deadzone=DefaultDeadzone=Zone;Values.Reset();Error.Reset();return true;
}
float UOAGDInputComponent::Strength(FName Action)const{return Values.FindRef(Action);}
FString UOAGDInputComponent::Binding(FName Action,int32 Slot)const{const auto* Row=Actions.Find(Action);return Row&&Row->Keys.IsValidIndex(Slot)?Row->Keys[Slot]:FString();}
void UOAGDInputComponent::Publish(){
 TArray<TPair<FName,float>> Changed;
 for(const auto& Pair:Actions){float Value=0;const auto& Row=Pair.Value;
  if(Capture.IsNone()&&(Row.Context==TEXT("global")||(Row.Context==Context.ToString()&&(Row.Context!=TEXT("game")||!IsPaused())))){
   for(const auto& Key:Row.Keys)if(!Blocked.Contains(Key))Value=FMath::Max(Value,Raw.FindRef(Key));
  }
  if(!FMath::IsNearlyEqual(Value,Strength(Pair.Key)))Changed.Emplace(Pair.Key,Value);
  Values.Add(Pair.Key,Value);
 }
 for(const auto& Pair:Changed)if(FMath::IsNearlyEqual(Strength(Pair.Key),Pair.Value))ActionChanged.Broadcast(Pair.Key,Pair.Value);
}
void UOAGDInputComponent::Barrier(){for(const auto& Pair:Raw)if(Pair.Value>0)Blocked.Add(Pair.Key);Publish();}
bool UOAGDInputComponent::SetContext(FName Value){if(Value!=TEXT("game")&&Value!=TEXT("ui"))return false;if(Context!=Value){Context=Value;CancelCapture();Barrier();}return true;}
void UOAGDInputComponent::SetPause(FName Reason,bool Active){if(Reason.IsNone())return;bool Before=IsPaused();if(Active)Pauses.Add(Reason);else Pauses.Remove(Reason);if(Before!=IsPaused()){Barrier();PauseChanged.Broadcast(IsPaused());}}
void UOAGDInputComponent::FocusLost(){CancelCapture();Raw.Reset();ModifierSources.Reset();Blocked.Reset();Publish();}
void UOAGDInputComponent::DisconnectPad(int32 Device){if(Device!=SelectedPad)return;for(auto It=Raw.CreateIterator();It;++It)if(It.Key().StartsWith(TEXT("Pad")))It.RemoveCurrent();for(auto It=Blocked.CreateIterator();It;++It)if(It->StartsWith(TEXT("Pad")))It.RemoveCurrent();SelectedPad=-1;CancelCapture();Publish();}
bool UOAGDInputComponent::HandleInput(const FInputKeyEventArgs& Args){
 if(Actions.IsEmpty())return false;
 if(Args.IsGamepad()){int32 Device=Args.InputDevice.GetId();if(SelectedPad<0)SelectedPad=Device;if(SelectedPad!=Device)return false;}
 if(Args.Key==EKeys::Gamepad_LeftX||Args.Key==EKeys::Gamepad_LeftY){
  const FString Base=Args.Key==EKeys::Gamepad_LeftX?TEXT("PadLeftX"):TEXT("PadLeftY");
  // Canonical Y is down-positive, matching Godot; UE native left-Y is up-positive.
  float Value=Args.AmountDepressed*(Args.Key==EKeys::Gamepad_LeftY?-1.f:1.f);
  Feed(Base+TEXT("+"),FMath::Max(Value,0.f));Feed(Base+TEXT("-"),FMath::Max(-Value,0.f));return true;
 }
 const FString Key=Token(Args.Key);if(Key.IsEmpty())return false;if(Args.Event==IE_Repeat)return true;
 if(Args.Event!=IE_Pressed&&Args.Event!=IE_Released)return false;
 if(Key==TEXT("Shift")||Key==TEXT("Ctrl")||Key==TEXT("Alt")){
  const FString Source=Args.Key.ToString();if(Args.Event==IE_Released)ModifierSources.Remove(Source);else ModifierSources.Add(Source,Key);
  bool Down=false;for(const auto& Pair:ModifierSources)if(Pair.Value==Key){Down=true;break;}
  return Feed(Key,Down?1.f:0.f);
 }
 // SceneViewport emits direction pressed/released AND MouseWheelAxis for the
 // same scroll. Only the direction channel has a token; the axis is ignored.
 return Feed(Key,Args.Event==IE_Released?0.f:1.f);
}
bool UOAGDInputComponent::Feed(const FString& Key,float Value){
 if(!Supported(Key)||!FMath::IsFinite(Value)||Actions.IsEmpty())return false;
 if(Key==TEXT("MouseWheelUp")||Key==TEXT("MouseWheelDown")){
  bool Handled=FeedState(Key,Value>0?1.f:0.f);if(Value>0)FeedState(Key,0.f);return Handled;
 }
 return FeedState(Key,Value);
}
bool UOAGDInputComponent::FeedState(const FString& Key,float Value){
 float Amount=FMath::Clamp(Value,0.f,1.f);if(Key.EndsWith(TEXT("+"))||Key.EndsWith(TEXT("-")))Amount=FMath::Max(0.f,(Amount-Deadzone)/(1.f-Deadzone));
 Raw.Add(Key,Amount);if(Amount==0)Blocked.Remove(Key);
 if(!Capture.IsNone()){
  if(Amount>=.5f&&!Blocked.Contains(Key)){
   if(Key==TEXT("Escape"))CancelCapture();
   else{FName Action=Capture;Capture=NAME_None;FString Error;bool Ok=Rebind(Action,CaptureSlot,Key,Error);Blocked.Add(Key);Publish();CaptureFinished.Broadcast(Ok,Ok?Key:Error);}
  }return true;
 }
 Publish();for(const auto& Pair:Actions)if(Pair.Value.Keys.Contains(Key)&&(Pair.Value.Context==Context.ToString()||Pair.Value.Context==TEXT("global")))return true;return false;
}
bool UOAGDInputComponent::Rebind(FName Action,int32 Slot,const FString& Key,FString& Error){
 const auto* Row=Actions.Find(Action);if(!Row||!Row->Rebindable||!Row->Keys.IsValidIndex(Slot)){Error=TEXT("Action or slot cannot be rebound");return false;}
 auto Candidate=Actions;Candidate[Action].Keys[Slot]=Key;if(!Validate(Candidate,Error))return false;Actions=Candidate;Barrier();Error.Reset();return true;
}
bool UOAGDInputComponent::BeginCapture(FName Action,int32 Slot){const auto* Row=Actions.Find(Action);if(Context!=TEXT("ui")||!Row||!Row->Rebindable||!Row->Keys.IsValidIndex(Slot))return false;Capture=Action;CaptureSlot=Slot;Barrier();return true;}
void UOAGDInputComponent::CancelCapture(){if(Capture.IsNone())return;Capture=NAME_None;Barrier();CaptureFinished.Broadcast(false,TEXT("Capture cancelled"));}
void UOAGDInputComponent::RestoreDefaults(){CancelCapture();Actions=Defaults;Deadzone=DefaultDeadzone;Barrier();}
FString UOAGDInputComponent::PreferencePath(const FString& Name){if(Name.IsEmpty()||Name.Contains(TEXT(".."))||Name.Contains(TEXT("/"))||Name.Contains(TEXT("\\"))||Name.Contains(TEXT(":")))return FString();return FPaths::ProjectSavedDir()/TEXT("OAGDInput")/Name;}
bool UOAGDInputComponent::SavePreferences(const FString& FileName,FString& Error)const{
 FString Path=PreferencePath(FileName);if(Path.IsEmpty()){Error=TEXT("Preferences require a local filename");return false;}
 auto Root=MakeShared<FJsonObject>();Root->SetStringField(TEXT("schema"),TEXT("oagd.input/1"));Root->SetStringField(TEXT("id"),ProfileId);Root->SetNumberField(TEXT("deadzone"),Deadzone);auto Rows=MakeShared<FJsonObject>();
 for(const auto& Pair:Actions){auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("context"),Pair.Value.Context);Row->SetBoolField(TEXT("rebindable"),Pair.Value.Rebindable);TArray<TSharedPtr<FJsonValue>> Keys;for(const auto& Key:Pair.Value.Keys)Keys.Add(MakeShared<FJsonValueString>(Key));Row->SetArrayField(TEXT("keys"),Keys);Rows->SetObjectField(Pair.Key.ToString(),Row);}
 Root->SetObjectField(TEXT("actions"),Rows);FString Text;FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Text));
 IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path),true);
 if(!FFileHelper::SaveStringToFile(Text,*(Path+TEXT(".tmp")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)||!IFileManager::Get().Move(*Path,*(Path+TEXT(".tmp")),true,false,false,true)){Error=TEXT("Preferences write/replace failed");return false;}Error.Reset();return true;
}
bool UOAGDInputComponent::LoadPreferences(const FString& FileName,FString& Error){
 FString Path=PreferencePath(FileName),Text,Id;float Zone;TMap<FName,FOAGDInputBinding> Candidate;
 if(Path.IsEmpty()||!FFileHelper::LoadFileToString(Text,*Path)){Error=TEXT("Cannot read preferences");return false;}
 if(!Parse(Text,Id,Zone,Candidate,Error))return false;
 if(Id!=ProfileId||Candidate.Num()!=Defaults.Num()){Error=TEXT("Profile mismatch");return false;}
 for(const auto& Pair:Defaults){const auto* Row=Candidate.Find(Pair.Key);const auto& Base=Pair.Value;
  if(!Row||Row->Context!=Base.Context||Row->Rebindable!=Base.Rebindable||Row->Keys.Num()!=Base.Keys.Num()||(!Base.Rebindable&&Row->Keys!=Base.Keys)){Error=TEXT("Action contract mismatch");return false;}
 }
 CancelCapture();Actions=Candidate;Deadzone=Zone;Barrier();Error.Reset();return true;
}
