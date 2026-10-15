#include "OAGDPlayback.h"
#include "OAGDLayers.h"
#include "Modules/ModuleManager.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimNode_SequencePlayer.h"
#include "Animation/AnimClassInterface.h"
#include "Animation/AnimInstanceProxy.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"
#include "UObject/UnrealType.h"
IMPLEMENT_MODULE(FDefaultModuleImpl,OAGDPlayback)

bool UOAGDPlaybackComponent::Validate() const {
 if(!Bindings||Bindings->Clips.IsEmpty()) return false;
 if(Bindings->RootMotionEnabled&&(Bindings->LocomotionEnabled||Bindings->LayersEnabled))return false;
 if(Bindings->LocomotionEnabled){
  if(!FMath::IsFinite(Bindings->WalkSpeedMps)||!FMath::IsFinite(Bindings->RunSpeedMps)||Bindings->WalkSpeedMps<=0||Bindings->RunSpeedMps<=Bindings->WalkSpeedMps||Bindings->RunSpeedMps>20)return false;
  for(FName Id:{FName(TEXT("idle")),FName(TEXT("walk")),FName(TEXT("run")),FName(TEXT("locomotion"))}){
   const auto* B=Bindings->Clips.FindByPredicate([Id](const auto& C){return C.Id==Id;});
   if(!B||!B->Loop||!B->Markers.IsEmpty())return false;
  }
 }
 TSet<FName> Ids; USkeleton* Skeleton=nullptr;
 for(const auto& B:Bindings->Clips) {
  if(B.Id.IsNone()||Ids.Contains(B.Id)||!B.Sequence||!B.Sequence->GetSkeleton()||B.Sequence->GetPlayLength()<=0) return false;
  const bool Rooted=B.MotionOwner==TEXT("animation");
  if(Rooted){if(!Bindings->RootMotionEnabled||B.ControllerOwned||B.Loop||B.LayerOnly||!B.Sequence->bEnableRootMotion)return false;}
  else if(B.MotionOwner!=TEXT("controller")||!B.ControllerOwned||B.Sequence->bEnableRootMotion)return false;
  Ids.Add(B.Id);
  if(Skeleton&&Skeleton!=B.Sequence->GetSkeleton())return false;
  Skeleton=B.Sequence->GetSkeleton();
  TSet<FName> Names;
  if(B.LayerOnly&&(!Bindings->LayersEnabled||!Bindings->LayerClips.Contains(B.Id)))return false;
  float LastMarker=-1;
  for(const auto& M:B.Markers) {
   if(M.Name.IsNone()||Names.Contains(M.Name)||!FMath::IsFinite(M.AtSeconds))return false;
   if(B.LayerOnly){if(M.AtSeconds<0||M.AtSeconds<LastMarker||M.AtSeconds>B.Sequence->GetPlayLength()||(B.Loop&&M.AtSeconds>=B.Sequence->GetPlayLength()))return false;LastMarker=M.AtSeconds;}
   else if(B.Loop||M.AtSeconds<=0||M.AtSeconds>=B.Sequence->GetPlayLength())return false;
   Names.Add(M.Name);
  }
 }
 return true;
}
FName UOAGDPlaybackComponent::Current() const {return Started&&Bindings&&Bindings->Clips.IsValidIndex(StateIndex)?Bindings->Clips[StateIndex].Id:NAME_None;}
bool UOAGDPlaybackComponent::SetLocomotionSpeed(float SpeedMps){
 if(!Bindings||!Bindings->LocomotionEnabled||!FMath::IsFinite(SpeedMps)||SpeedMps<0||SpeedMps>20||!Validate())return false;
 const auto* Walk=Bindings->Clips.FindByPredicate([](const auto& C){return C.Id==TEXT("walk");});
 const auto* Run=Bindings->Clips.FindByPredicate([](const auto& C){return C.Id==TEXT("run");});
 MoveWeight=FMath::Clamp(SpeedMps/Bindings->WalkSpeedMps,0.f,1.f);
 RunWeight=FMath::Clamp((SpeedMps-Bindings->WalkSpeedMps)/(Bindings->RunSpeedMps-Bindings->WalkSpeedMps),0.f,1.f);
 const float Stride=FMath::Lerp(Bindings->WalkSpeedMps*Walk->Sequence->GetPlayLength(),Bindings->RunSpeedMps*Run->Sequence->GetPlayLength(),RunWeight);
 CycleHz=SpeedMps/FMath::Max(MoveWeight*Stride,1.e-6f);return true;
}
bool UOAGDPlaybackComponent::Select(FName Action) {
 if(Changing||!Validate())return false;
 int32 Index=Bindings->Clips.IndexOfByPredicate([Action](const auto& B){return B.Id==Action;});
 if(Index==INDEX_NONE||Bindings->Clips[Index].LayerOnly)return false;
 if(Started&&Index==StateIndex)return true;
 TGuardValue<bool> Guard(Changing,true);
 if(Started&&!Finished)Ended.Broadcast(Current(),Generation,TEXT("interrupted"));
 StateIndex=Index;Started=true;++Generation;PositionSeconds=0;Finished=false;ObservedStart=false;Fired.Empty();return true;
}
bool UOAGDPlaybackComponent::SetRate(float Value) {if(!FMath::IsFinite(Value)||Value<0||Value>4)return false;Rate=Value;return true;}
void UOAGDPlaybackComponent::Reset(FName Action) {
 if(Changing||!Validate()||!Bindings->Clips.ContainsByPredicate([Action](const auto& B){return B.Id==Action&&!B.LayerOnly;}))return;
 {TGuardValue<bool> Guard(Changing,true);if(Started&&!Finished)Ended.Broadcast(Current(),Generation,TEXT("reset"));}
 Started=false;Select(Action);
 if(GetOwner())if(auto* Mesh=GetOwner()->FindComponentByClass<USkeletalMeshComponent>())Mesh->InitAnim(true);
}
void UOAGDPlaybackComponent::Sample(UAnimSequence* Sequence,float Time,float FirstStepSeconds) {
 if(!Started||!Bindings||!Bindings->Clips.IsValidIndex(StateIndex)||!FMath::IsFinite(Time)||Time<0)return;
 const auto B=Bindings->Clips[StateIndex];
 if(B.Sequence!=Sequence)return;
 // A zero-weight child can retain a cached nonzero weight and its previous end
 // time until the newly selected graph input has actually activated. Generation
 // equality alone does not prove that this sequence was reset for that request.
 // Admit the first sample only at a real start (including short clips that finish
 // inside their first engine step); never synthesize a seek or restart event.
 if(!ObservedStart&&!B.Loop){
  if(Time>FMath::Max(0.f,FirstStepSeconds)+1.e-4f)return;
  ObservedStart=true;
 }
 PositionSeconds=Time;
 if(Finished||B.Loop)return;
 const int32 Token=Generation;
 for(const auto& M:B.Markers)if(Time+1.e-6f>=M.AtSeconds&&!Fired.Contains(M.Name)) {
  Fired.Add(M.Name);Marker.Broadcast(B.Id,Token,M.Name);
  if(Generation!=Token)return;
 }
 if(Time>=B.Sequence->GetPlayLength()-1.e-4f){Finished=true;Ended.Broadcast(B.Id,Token,TEXT("completed"));}
}
void UOAGDPlaybackAnimInstance::NativeUpdateAnimation(float Delta) {
 Super::NativeUpdateAnimation(Delta);
 EvaluationDelta=Delta;
 // Keep pose evaluation native. No manual SetPosition or TickAnimation calls.
 if(auto* Owner=GetOwningActor())if(auto* P=Owner->FindComponentByClass<UOAGDPlaybackComponent>()){
  StateIndex=P->StateIndex;PlaybackRate=P->Rate;EvaluatedGeneration=P->Generation;
  if(InitializedRequest!=P->Generation&&P->Bindings&&P->Bindings->Clips.IsValidIndex(StateIndex)){
   const auto& Requested=P->Bindings->Clips[StateIndex];
   // UE ResetChildOnActivate resets only a zero-weight child. A non-looping
   // action requested again during its fade-out must start a fresh player too.
   // Reinitialize once per request; time then advances solely in the native graph.
   if(!Requested.Loop)if(auto* Interface=IAnimClassInterface::GetFromClass(GetClass())){
    FAnimationInitializeContext Context(&GetProxyOnGameThread<FAnimInstanceProxy>());
    for(auto* Property:Interface->GetAnimNodeProperties())if(Property&&Property->Struct->IsChildOf(FAnimNode_SequencePlayerBase::StaticStruct())){
     auto* Node=Property->ContainerPtrToValuePtr<FAnimNode_SequencePlayerBase>(this);
     if(Node->GetSequence()==Requested.Sequence)Node->Initialize_AnyThread(Context);
    }
   }
   InitializedRequest=P->Generation;
  }
  MoveWeight=P->MoveWeight;RunWeight=P->RunWeight;
  if(P->Bindings&&P->Bindings->LocomotionEnabled)for(const auto& B:P->Bindings->Clips){
   if(B.Id==TEXT("walk"))WalkRate=P->CycleHz*B.Sequence->GetPlayLength()*P->Rate;
   if(B.Id==TEXT("run"))RunRate=P->CycleHz*B.Sequence->GetPlayLength()*P->Rate;
  }
 }
 if(auto* Owner=GetOwningActor())if(auto* L=Owner->FindComponentByClass<UOAGDLayersComponent>())if(L->Bindings){
  L->AdvanceEnvelopes(Delta*PlaybackRate);
  UpperWeight=L->Upper.Weight;FullWeight=L->Full.Weight;UpperMix=L->Upper.Mix;FullMix=L->Full.Mix;
  Upper0=L->Upper.Sequence0;Upper1=L->Upper.Sequence1;Full0=L->Full.Sequence0;Full1=L->Full.Sequence1;
  UpperRate0=L->Upper.Rate0*PlaybackRate;UpperRate1=L->Upper.Rate1*PlaybackRate;FullRate0=L->Full.Rate0*PlaybackRate;FullRate1=L->Full.Rate1*PlaybackRate;
  UpperLoop0=L->Upper.Loop0;UpperLoop1=L->Upper.Loop1;FullLoop0=L->Full.Loop0;FullLoop1=L->Full.Loop1;
  if(auto* Interface=IAnimClassInterface::GetFromClass(GetClass())){
   FAnimationInitializeContext Context(&GetProxyOnGameThread<FAnimInstanceProxy>());
   for(auto* Property:Interface->GetAnimNodeProperties())if(Property&&Property->Struct==FAnimNode_SequencePlayer::StaticStruct()){
    auto* Node=Property->ContainerPtrToValuePtr<FAnimNode_SequencePlayer>(this);const FName Tag=Node->GetGroupName();
    const FString Name=Tag.ToString();if(!Name.StartsWith(TEXT("OAGDLayer_")))continue;
    const bool IsUpper=Name.Contains(TEXT("upper"));const int32 Bank=Name.EndsWith(TEXT("0"))?0:1;
    const auto& S=IsUpper?L->Upper:L->Full;const int32 Token=Bank==0?S.BankRun0:S.BankRun1;
    LayerEvaluated.Add(Tag,Token);
    if(!LayerInitialized.Contains(Tag)||LayerInitialized[Tag]!=Token){
     Node->SetSequence(Bank==0?S.Sequence0:S.Sequence1);Node->SetLoopAnimation(Bank==0?S.Loop0:S.Loop1);Node->Initialize_AnyThread(Context);LayerInitialized.Add(Tag,Token);
    }
   }
  }
 }
 bool RootEnabled=false;
 if(auto* Owner=GetOwningActor())if(auto* P=Owner->FindComponentByClass<UOAGDPlaybackComponent>())RootEnabled=P->Bindings&&P->Bindings->RootMotionEnabled;
 SetRootMotionMode(RootEnabled?ERootMotionMode::RootMotionFromEverything:ERootMotionMode::IgnoreRootMotion);
}
void UOAGDPlaybackAnimInstance::NativePostEvaluateAnimation() {
 Super::NativePostEvaluateAnimation();
 auto* Owner=GetOwningActor();if(!Owner)return;
 auto* P=Owner->FindComponentByClass<UOAGDPlaybackComponent>();if(!P)return;
 const bool BaseCurrent=P->Generation==EvaluatedGeneration&&StateIndex==P->StateIndex;
 auto* L=Owner->FindComponentByClass<UOAGDLayersComponent>();
 auto* Interface=IAnimClassInterface::GetFromClass(GetClass());if(!Interface)return;
 for(const auto& Field:Interface->GetAnimNodeProperties()) {
  auto* Property=Field;
  if(Property&&Property->Struct->IsChildOf(FAnimNode_SequencePlayerBase::StaticStruct())) {
   auto* Node=Property->ContainerPtrToValuePtr<FAnimNode_SequencePlayerBase>(this);
   const FName Tag=Node->GetGroupName();const FString Name=Tag.ToString();
   if(Name.StartsWith(TEXT("OAGDLayer_"))){
    if(L&&LayerEvaluated.Contains(Tag)&&Node->GetCachedBlendWeight()>1.e-6f){
     const auto* Record=Node->GetDeltaTimeRecord();
     if(Record&&Record->IsPreviousValid())L->Sample(Name.Contains(TEXT("upper"))?TEXT("upper"):TEXT("full"),Name.EndsWith(TEXT("0"))?0:1,LayerEvaluated[Tag],Node->GetCurrentAssetTime(),Record->Delta);
    }
    continue;
   }
   if(Node->GetGroupName()==TEXT("OAGDLocomotion")){
    for(const auto& B:P->Bindings->Clips)if(B.Sequence==Node->GetSequence()){
     if(B.Id==TEXT("walk"))P->WalkTime=Node->GetCurrentAssetTime();
     if(B.Id==TEXT("run"))P->RunTime=Node->GetCurrentAssetTime();
    }
   }
   // Inactive players retain their old end time. Never replay those old markers
   // on the frame between a new request and the graph activating/resetting it.
   if(BaseCurrent&&Node->GetCachedBlendWeight()>1.e-6f)P->Sample(Cast<UAnimSequence>(Node->GetSequence()),Node->GetCurrentAssetTime(),EvaluationDelta*P->Rate);
  }
 }
}
