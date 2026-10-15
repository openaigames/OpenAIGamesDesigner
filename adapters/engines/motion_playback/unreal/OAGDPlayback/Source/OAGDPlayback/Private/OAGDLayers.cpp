#include "OAGDLayers.h"
#include "OAGDPlayback.h"
#include "Animation/AnimSequence.h"
#include "Animation/Skeleton.h"

FOAGDLayerState* UOAGDLayersComponent::State(FName C){return C==TEXT("upper")?&Upper:C==TEXT("full")?&Full:nullptr;}
bool UOAGDLayersComponent::Configure(UOAGDPlaybackSet* B){
 if(!B||!B->LayersEnabled||B->LayerClips.IsEmpty()||B->UpperRoot.IsNone())return false;
 for(float V:{B->LayerFadeIn,B->LayerFadeOut,B->LayerReplace})if(!FMath::IsFinite(V)||V<.04f||V>1)return false;
 auto* Validator=NewObject<UOAGDPlaybackComponent>(this);Validator->Bindings=B;if(!Validator->Validate())return false;
 TSet<FName> Ids;
 for(FName Id:B->LayerClips){
  const auto* Row=B->Clips.FindByPredicate([Id](const auto& C){return C.Id==Id;});
  if(Ids.Contains(Id)||!Row||!Row->LayerOnly||Id==B->DefaultAction)return false;Ids.Add(Id);
 }
 const auto* Clip=B->Clips.FindByPredicate([B](const auto& C){return C.Id==B->LayerClips[0];});
 if(!Clip||!Clip->LayerOnly||!Clip->Sequence)return false;
 const auto& Ref=Clip->Sequence->GetSkeleton()->GetReferenceSkeleton();const int32 Root=Ref.FindBoneIndex(B->UpperRoot);
 if(Root<=0||B->UpperRequiredBones.IsEmpty()||B->LowerExcludedBones.IsEmpty())return false;
 auto Included=[&](FName Name){int32 Bone=Ref.FindBoneIndex(Name);while(Bone!=INDEX_NONE){if(Bone==Root)return true;Bone=Ref.GetParentIndex(Bone);}return false;};
 for(FName Name:B->UpperRequiredBones)if(!Included(Name))return false;
 for(FName Name:B->LowerExcludedBones)if(Ref.FindBoneIndex(Name)==INDEX_NONE||Included(Name))return false;
 Bindings=B;Upper=FOAGDLayerState();Full=FOAGDLayerState();
 for(auto* S:{&Upper,&Full})S->Sequence0=S->Sequence1=Clip->Sequence;
 return true;
}
bool UOAGDLayersComponent::Play(FName C,FName A,int32 Priority,float Weight,float Speed,bool Restart){
 Rejection=NAME_None;
 if(Changing){Rejection=TEXT("reentrant_request");return false;}
 auto* S=State(C);
 if(!Bindings||!S||!Bindings->LayerClips.Contains(A)){Rejection=TEXT("invalid_binding");return false;}
 if(!FMath::IsFinite(Weight)||Weight<=.001f||Weight>1||!FMath::IsFinite(Speed)||Speed<0||Speed>4){Rejection=TEXT("invalid_parameter");return false;}
 if(C==TEXT("upper")&&(Full.Active||Full.Weight>1.e-6f)){Rejection=TEXT("full_override");return false;}
 if(S->Active&&Priority<S->Priority){Rejection=TEXT("priority");return false;}
 if(S->Active&&S->Action==A&&!Restart)return true;
 if(S->Weight>1.e-6f&&FMath::Abs(S->Mix-S->Bank)>1.e-6f){Rejection=TEXT("transition_busy");return false;}
 const auto* Clip=Bindings->Clips.FindByPredicate([A](const auto& B){return B.Id==A;});
 if(!Clip||!Clip->LayerOnly||!Clip->Sequence){Rejection=TEXT("invalid_binding");return false;}
 TGuardValue<bool> Guard(Changing,true);
 if(C==TEXT("full"))End(TEXT("upper"),TEXT("overridden"));
 End(C,TEXT("interrupted"));
 ++S->Run;S->Bank=1-S->Bank;S->Action=A;S->Active=true;S->Target=Weight;S->Rate=Speed;S->Priority=Priority;S->PositionSeconds=0;S->TotalSeconds=0;S->First=true;
 if(S->Weight<=1.e-6f)S->Mix=S->Bank;
 if(S->Bank==0){S->Sequence0=Clip->Sequence;S->Rate0=Speed;S->Loop0=Clip->Loop;S->BankRun0=S->Run;}
 else{S->Sequence1=Clip->Sequence;S->Rate1=Speed;S->Loop1=Clip->Loop;S->BankRun1=S->Run;}
 return true;
}
void UOAGDLayersComponent::Emit(FName C,FName Kind,FName Name,int32 Cycle,float At){
 auto* S=State(C);FOAGDLayerEvent E;E.Channel=C;E.Action=S->Action;E.Run=S->Run;E.Kind=Kind;E.Name=Name;E.Cycle=Cycle;E.AtSeconds=At;E.PositionSeconds=S->PositionSeconds;E.TotalSeconds=S->TotalSeconds;E.Weight=S->Weight;Event.Broadcast(E);
}
void UOAGDLayersComponent::End(FName C,FName Reason){
 auto* S=State(C);if(!S||!S->Active)return;
 S->Active=false;S->Target=0;
 const auto* B=Bindings->Clips.FindByPredicate([S](const auto& Row){return Row.Id==S->Action;});
 Emit(C,TEXT("ended"),Reason,FMath::FloorToInt(S->TotalSeconds/B->Sequence->GetPlayLength()),S->PositionSeconds);
}
bool UOAGDLayersComponent::Cancel(FName C,FName Reason){if(Changing||!State(C))return false;TGuardValue<bool> G(Changing,true);End(C,Reason);return true;}
bool UOAGDLayersComponent::SetLayerWeight(FName C,float V){
 auto* S=State(C);if(Changing||!S||!FMath::IsFinite(V)||V<0||V>1)return false;
 if(V<=.001f)return Cancel(C,TEXT("weight_zero"));if(!S->Active)return false;S->Target=V;return true;
}
bool UOAGDLayersComponent::SetLayerRate(FName C,float V){
 auto* S=State(C);if(Changing||!S||!FMath::IsFinite(V)||V<0||V>4)return false;
 S->Rate=V;if(S->Bank==0)S->Rate0=V;else S->Rate1=V;return true;
}
void UOAGDLayersComponent::ResetLayers(){
 if(Changing)return;TGuardValue<bool> G(Changing,true);
 for(FName C:{FName(TEXT("upper")),FName(TEXT("full"))}){End(C,TEXT("reset"));auto* S=State(C);++S->Run;S->Action=NAME_None;S->Weight=S->Target=0;S->PositionSeconds=0;S->TotalSeconds=0;S->Rate0=S->Rate1=0;}
}
void UOAGDLayersComponent::AdvanceEnvelopes(float Delta){
 if(!Bindings||!FMath::IsFinite(Delta)||Delta<0)return;
 for(auto* S:{&Upper,&Full}){
  const float Fade=S->Target>S->Weight?Bindings->LayerFadeIn:Bindings->LayerFadeOut;
  S->Weight=FMath::FInterpConstantTo(S->Weight,S->Target,Delta,1/Fade);
  S->Mix=FMath::FInterpConstantTo(S->Mix,float(S->Bank),Delta,1/Bindings->LayerReplace);
 }
}
void UOAGDLayersComponent::Sample(FName C,int32 Bank,int32 Token,float Position,float NativeDelta){
 auto* S=State(C);if(!Bindings||!S||!S->Active||S->Bank!=Bank||S->Run!=Token)return;
 const auto B=*Bindings->Clips.FindByPredicate([S](const auto& Row){return Row.Id==S->Action;});
 const double Duration=B.Sequence->GetPlayLength();
 if(!FMath::IsFinite(Position)||!FMath::IsFinite(NativeDelta)||NativeDelta<0)return;
 const double Previous=S->First?-2.e-6:S->TotalSeconds;
 double Total=S->First?NativeDelta:S->TotalSeconds+NativeDelta;
 if(!B.Loop)Total=FMath::Min(Total,Duration);
 const double Expected=B.Loop?FMath::Fmod(Total,Duration):Total;
 double Error=FMath::Abs(Position-Expected);if(B.Loop)Error=FMath::Min(Error,FMath::Abs(Error-Duration));
 if(Error>.002){++ClockFaults;Cancel(C,TEXT("clock_mismatch"));return;}
 S->First=false;S->PositionSeconds=Position;S->TotalSeconds=Total;
 const int32 FirstCycle=FMath::Max(0,FMath::FloorToInt(FMath::Max(Previous,0.)/Duration));
 const int32 LastCycle=B.Loop?FMath::FloorToInt((Total+1.e-6)/Duration):0;
 for(int32 Cycle=FirstCycle;Cycle<=LastCycle;++Cycle){
  for(const auto& M:B.Markers){
   const double At=M.AtSeconds+Cycle*Duration;
   if(At>Previous+1.e-6&&At<=Total+1.e-6&&S->Weight>.001f){Emit(C,TEXT("marker"),M.Name,Cycle,M.AtSeconds);if(!S->Active||S->Run!=Token)return;}
  }
 }
 if(S->Active&&S->Run==Token&&!B.Loop&&Total>=Duration-1.e-5)End(C,TEXT("completed"));
}
