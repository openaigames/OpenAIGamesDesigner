#include "OAGDFeedback.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundWave.h"
#include "Sound/SoundAttenuation.h"
#include "Engine/World.h"
#include "Misc/App.h"

UOAGDFeedbackComponent::UOAGDFeedbackComponent(){PrimaryComponentTick.bCanEverTick=true;PrimaryComponentTick.bTickEvenWhenPaused=true;}
bool UOAGDFeedbackComponent::Configure(const TMap<FName,FOAGDFeedbackCue>& Bindings,int32 Budget,FString& Error){
 Error.Reset();if(Emitting){Error=TEXT("defer play/configure until lifecycle callback returns");return false;}if(Active.Num()){Error=TEXT("cannot reconfigure active feedback");return false;}
 if(Budget<1||Budget>32||Bindings.IsEmpty()||Bindings.Num()>128){Error=TEXT("invalid feedback budget");return false;}
 for(const auto& Pair:Bindings){const auto& C=Pair.Value;
  if(Pair.Key.IsNone()||Pair.Key.ToString().Len()>80||C.Limit<1||C.Limit>16||!FMath::IsFinite(C.Duration)||C.Duration<.02||C.Duration>60||!FMath::IsFinite(C.Volume)||C.Volume<0||C.Volume>1||!FMath::IsFinite(C.Camera)||C.Camera<0||C.Camera>3||(!FMath::IsFinite(C.Color.R)||!FMath::IsFinite(C.Color.G)||!FMath::IsFinite(C.Color.B))||C.Color.R<0||C.Color.R>1||C.Color.G<0||C.Color.G>1||C.Color.B<0||C.Color.B>1||(C.Loop&&C.UI)){Error=TEXT("invalid feedback cue");return false;}
  if(C.Visual&&C.Visual->HasAnyClassFlags(CLASS_Abstract)){Error=TEXT("visual class is abstract");return false;}
  if(auto* Wave=Cast<USoundWave>(C.Sound);Wave&&bool(Wave->bLooping)!=C.Loop){Error=TEXT("audio loop binding mismatch");return false;}
 }
 Cues=Bindings;MaxActive=Budget;Seen.Reset();return true;
}
int32 UOAGDFeedbackComponent::Reject(const TCHAR* Error){LastError=Error;return -1;}
int32 UOAGDFeedbackComponent::Play(FName Cue,const FString& Event,AActor* Owner,FVector Position,bool Follow,const FString& Scope,float Intensity){
 LastError.Reset();if(Emitting)return Reject(TEXT("defer play/configure until lifecycle callback returns"));const auto* Spec=Cues.Find(Cue);
 if(!Spec||Event.IsEmpty()||Event.Len()>120||Scope.IsEmpty()||Position.ContainsNaN()||!FMath::IsFinite(Intensity)||Intensity<0||Intensity>2)return Reject(TEXT("invalid feedback request"));
 if(GamePaused&&!Spec->UI)return Reject(TEXT("game feedback paused"));
 if((Follow||Spec->Loop)&&!IsValid(Owner))return Reject(TEXT("follow/loop requires live owner"));
 if(Seen.Contains(Event))return Reject(TEXT("duplicate event"));
 TArray<int32> Same;for(const auto& Pair:Active)if(Pair.Value.Cue==Cue)Same.Add(Pair.Key);Same.Sort();int32 Replace=-1;
 if(Same.Num()>=Spec->Limit){if(!Spec->ReplaceOldest)return Reject(TEXT("cue concurrency limit"));Replace=Same[0];}
 if(Active.Num()>=MaxActive&&Replace==-1)return Reject(TEXT("global concurrency limit"));
 FOAGDFeedbackInstance Item;Item.Cue=Cue;Item.Event=Event;Item.Scope=Scope;Item.Owner=Owner;Item.HasOwner=IsValid(Owner);Item.Follow=Follow;Item.Offset=Position;Item.Strength=Intensity;
 const FVector At=Follow?Owner->GetActorLocation()+Position:Position;
 if(Spec->Visual){Item.Visual=GetWorld()->SpawnActor<AOAGDFeedbackVisual>(Spec->Visual,At,FRotator::ZeroRotator);if(!Item.Visual)return Reject(TEXT("visual spawn failed"));Item.Visual->Sample(0,Intensity,Spec->Color);}
 if(Replace!=-1)Stop(Replace,TEXT("replaced"));
 if((Follow||Spec->Loop)&&!IsValid(Owner)){if(IsValid(Item.Visual))Item.Visual->Destroy();return Reject(TEXT("owner ended during replacement"));}
 if(Spec->Sound){Item.Audio=NewObject<UAudioComponent>(GetOwner());Item.Audio->bAutoActivate=false;Item.Audio->bAutoDestroy=false;Item.Audio->bIsUISound=true;Item.Audio->bAllowSpatialization=Spec->Spatial;Item.Audio->RegisterComponentWithWorld(GetWorld());Item.Audio->SetWorldLocation(At);Item.Audio->SetSound(Spec->Sound);Item.Audio->SetVolumeMultiplier(Spec->Volume*Intensity);
  if(Spec->Spatial){FSoundAttenuationSettings Attenuation;Attenuation.bAttenuate=true;Attenuation.bSpatialize=true;Attenuation.AttenuationShapeExtents=FVector(400);Attenuation.FalloffDistance=2100;Item.Audio->AdjustAttenuation(Attenuation);}Item.Audio->Play();}
 const int32 Handle=++Next;Active.Add(Handle,Item);Seen.Add(Event);if(Seen.Num()>256)Seen.RemoveAt(0);Emit(Handle,Event,Cue,TEXT("started"));return Handle;
}
void UOAGDFeedbackComponent::Emit(int32 Handle,const FString& Event,FName Cue,const FString& State){TGuardValue<bool> Guard(Emitting,true);Lifecycle.Broadcast(Handle,Event,Cue,State);}
bool UOAGDFeedbackComponent::Stop(int32 Handle,const FString& Reason){auto* Found=Active.Find(Handle);if(!Found)return false;const auto Item=*Found;Active.Remove(Handle);if(IsValid(Item.Audio)){Item.Audio->Stop();Item.Audio->DestroyComponent();}if(IsValid(Item.Visual))Item.Visual->Destroy();Emit(Handle,Item.Event,Item.Cue,Reason);RecomputeCamera();return true;}
void UOAGDFeedbackComponent::StopScope(const FString& Scope){TArray<int32> Keys;Active.GetKeys(Keys);for(int32 Key:Keys)if(Active.Contains(Key)&&Active[Key].Scope==Scope)Stop(Key,TEXT("scope-ended"));}
void UOAGDFeedbackComponent::Clear(){TArray<int32> Keys;Active.GetKeys(Keys);for(int32 Key:Keys)Stop(Key,TEXT("cleared"));Seen.Reset();CameraOffset=FRotator::ZeroRotator;}
void UOAGDFeedbackComponent::SetGamePaused(bool Value){GamePaused=Value;for(auto& Pair:Active)if(IsValid(Pair.Value.Audio))Pair.Value.Audio->SetPaused(Value&&!Cues[Pair.Value.Cue].UI);}
void UOAGDFeedbackComponent::TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick){
 Super::TickComponent(Delta,Type,Tick);const double Now=FPlatformTime::Seconds();const float Wall=LastWall>0?float(Now-LastWall):0;LastWall=Now;TArray<int32> Keys;Active.GetKeys(Keys);
 for(int32 Key:Keys){if(!Active.Contains(Key))continue;auto& Item=Active[Key];const auto& Spec=Cues[Item.Cue];
  if(Item.HasOwner&&!Item.Owner.IsValid()){Stop(Key,TEXT("owner-ended"));continue;}
  if(Item.Follow){const FVector At=Item.Owner->GetActorLocation()+Item.Offset;if(IsValid(Item.Visual))Item.Visual->SetActorLocation(At);if(IsValid(Item.Audio))Item.Audio->SetWorldLocation(At);}
  if(GamePaused&&!Spec.UI)continue;
  Item.Age+=Spec.UI?Wall:Delta;
  if(!Spec.Loop&&Item.Age>=Spec.Duration){Stop(Key,TEXT("finished"));continue;}
  if(IsValid(Item.Visual))Item.Visual->Sample(Item.Age,Item.Strength,Spec.Color);
 }
 RecomputeCamera();
}
void UOAGDFeedbackComponent::RecomputeCamera(){float Angle=0;for(const auto& Pair:Active){const auto& Item=Pair.Value;const auto& Spec=Cues[Item.Cue];const float Envelope=Spec.Loop?1:FMath::Max(0.f,1-Item.Age/Spec.Duration);Angle+=FMath::Sin(Item.Age*35)*Spec.Camera*Item.Strength*Envelope;}CameraOffset=FRotator(FMath::Clamp(Angle,-3.f,3.f),0,FMath::Clamp(Angle*.5f,-1.5f,1.5f));}
void UOAGDFeedbackComponent::EndPlay(const EEndPlayReason::Type Reason){Clear();Super::EndPlay(Reason);}
