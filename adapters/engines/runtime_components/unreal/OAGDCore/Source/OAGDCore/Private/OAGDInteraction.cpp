#include "OAGDInteraction.h"
#include "OAGDComponents.h"
#include "GameFramework/Actor.h"

FVector UOAGDInteractableComponent::Anchor()const{return GetOwner()->GetActorLocation()+AnchorOffset;}
bool UOAGDInteractionComponent::Configure(float Distance,float Angle){if(Notifying||Committing||Holding()||!FMath::IsFinite(Distance)||Distance<=0||Distance>10000||!FMath::IsFinite(Angle)||Angle<=0||Angle>89)return false;Range=Distance;HalfAngle=Angle;return true;}
bool UOAGDInteractionComponent::ValidSpec(UOAGDInteractableComponent* T)const{return IsValid(T)&&IsValid(T->GetOwner())&&!T->StableId.IsEmpty()&&T->StableId.Len()<=80&&!T->Prompt.IsEmpty()&&T->Prompt.Len()<=160&&FMath::IsFinite(T->HoldSeconds)&&T->HoldSeconds>=0&&T->HoldSeconds<=10&&!T->Anchor().ContainsNaN();}
bool UOAGDInteractionComponent::RegisterTarget(UOAGDInteractableComponent* T){if(Notifying||Committing||!ValidSpec(T))return false;auto* Old=Targets.Find(T->StableId);if(Old&&Old->IsValid())return Old->Get()==T;if(Targets.Num()>=128)return false;Targets.Add(T->StableId,T);return true;}
void UOAGDInteractionComponent::UnregisterTarget(const FString& Id){Targets.Remove(Id);if(TargetId==Id)Cancel(TEXT("unregistered"));if(FocusedId()==Id)SetFocus(nullptr);}
FString UOAGDInteractionComponent::FocusedId()const{return Focus.IsValid()?Focus->StableId:FString();}
bool UOAGDInteractionComponent::Visible(UOAGDInteractableComponent* T)const{const FVector Offset=T->Anchor()-Origin;FHitResult Hit;return !UOAGDQuery::VisibleHit(const_cast<UOAGDInteractionComponent*>(this),Origin,Offset,float(Offset.Size())+1,Actor.Get(),Hit)||Hit.GetActor()==T->GetOwner();}
void UOAGDInteractionComponent::SetFocus(UOAGDInteractableComponent* T){Focus=T;Prompt=T?T->Prompt:FString();Reason.Reset();Allowed=false;if(T){const auto Offer=T->Query(Actor.Get());Allowed=Offer.Allowed;Reason=Offer.Reason;}}
void UOAGDInteractionComponent::Refresh(){
 if(Suspended||!HasView||!Actor.IsValid()){SetFocus(nullptr);return;}
 UOAGDInteractableComponent* Best=nullptr;double BestAngle=DBL_MAX,BestDistance=DBL_MAX;FString BestId;TArray<FString> Keys;Targets.GetKeys(Keys);
 for(const auto& Id:Keys){auto* T=Targets[Id].Get();if(!IsValid(T)||!IsValid(T->GetOwner())){Targets.Remove(Id);continue;}if(!ValidSpec(T)||T->StableId!=Id||!T->Enabled)continue;
  const FVector Offset=T->Anchor()-Origin;const double Distance=Offset.Size();if(Distance>Range)continue;const double Alignment=Distance>.1?FVector::DotProduct(Direction,Offset.GetSafeNormal()):1;
  if(Alignment<FMath::Cos(FMath::DegreesToRadians(HalfAngle))||!Visible(T))continue;const double Angle=1-Alignment;
  if(Angle<BestAngle-.00001||(FMath::Abs(Angle-BestAngle)<=.00001&&(Distance<BestDistance-.1||(FMath::Abs(Distance-BestDistance)<=.1&&Id<BestId)))){Best=T;BestAngle=Angle;BestDistance=Distance;BestId=Id;}
 }SetFocus(Best);
}
void UOAGDInteractionComponent::UpdateQuery(AActor* Requester,FVector At,FVector Forward,float Delta){
 if(Notifying||Committing)return;
 if(!IsValid(Requester)||At.ContainsNaN()||Forward.ContainsNaN()||Forward.SizeSquared()<.0001||!FMath::IsFinite(Delta)||Delta<0){HasView=false;Cancel(TEXT("invalid query"));SetFocus(nullptr);return;}
 if(Holding()&&Actor.Get()!=Requester)Cancel(TEXT("requester changed"));Actor=Requester;Origin=At;Direction=Forward.GetSafeNormal();HasView=true;Refresh();
 if(!Holding())return;if(!Pending.IsValid()||!IsValid(Pending->GetOwner())){Cancel(TEXT("target ended"));return;}if(Focus!=Pending){Cancel(TEXT("focus lost"));return;}if(!Allowed){Cancel(Reason);return;}
 Elapsed+=Delta;Progress=FMath::Clamp(Elapsed/FMath::Max(Duration,.00001f),0.f,1.f);if(Elapsed>=Duration)Finish();
}
bool UOAGDInteractionComponent::Reject(const TCHAR* Message){LastError=Message;return false;}
bool UOAGDInteractionComponent::Begin(const FString& Request){
 LastError.Reset();if(Notifying||Committing)return Reject(TEXT("defer begin until callback returns"));if(Suspended||Holding())return Reject(TEXT("paused or busy"));if(Request.IsEmpty()||Request.Len()>120||Seen.Contains(Request))return Reject(TEXT("invalid or duplicate request"));Refresh();
 auto* T=Focus.Get();if(!T||!Allowed){LastError=T?Reason:TEXT("no target");return false;}RequestId=Request;TargetId=T->StableId;Pending=T;Elapsed=0;Progress=0;Duration=T->HoldSeconds;
 Seen.Add(Request);if(Seen.Num()>256)Seen.RemoveAt(0);Emit(RequestId,TargetId,TEXT("started"),TEXT(""));if(Holding()&&Duration==0)Finish();return true;
}
void UOAGDInteractionComponent::Finish(){Refresh();auto* T=Pending.Get();auto* A=Actor.Get();if(!T||!A||Focus!=Pending||!Allowed){Cancel(TEXT("condition changed before commit"));return;}const FString Request=RequestId,Id=TargetId;RequestId.Reset();TargetId.Reset();Pending.Reset();Progress=0;bool Success;{TGuardValue<bool> Guard(Committing,true);Success=T->Execute(A);}Emit(Request,Id,Success?TEXT("completed"):TEXT("failed"),Success?TEXT(""):TEXT("project commit rejected"));Refresh();}
bool UOAGDInteractionComponent::Cancel(const FString& Detail){if(!Holding())return false;const FString Request=RequestId,Id=TargetId;RequestId.Reset();TargetId.Reset();Pending.Reset();Progress=0;Emit(Request,Id,TEXT("cancelled"),Detail);return true;}
void UOAGDInteractionComponent::SetSuspended(bool Value){Suspended=Value;if(Value){Cancel(TEXT("paused"));SetFocus(nullptr);}}
void UOAGDInteractionComponent::Clear(){Targets.Reset();HasView=false;SetFocus(nullptr);Cancel(TEXT("scene ended"));Seen.Reset();}
void UOAGDInteractionComponent::Emit(const FString& Request,const FString& Id,const FString& State,const FString& Detail){TGuardValue<bool> Guard(Notifying,true);const FString R=Request,I=Id,S=State,D=Detail;Lifecycle.Broadcast(R,I,S,D);}
void UOAGDInteractionComponent::EndPlay(const EEndPlayReason::Type Detail){Clear();Super::EndPlay(Detail);}
