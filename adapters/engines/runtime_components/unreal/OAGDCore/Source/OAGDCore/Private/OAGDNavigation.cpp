#include "OAGDNavigation.h"
#include "NavigationSystem.h"
#include "NavigationPath.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"

namespace { bool Finite(FVector V){return FMath::IsFinite(V.X)&&FMath::IsFinite(V.Y)&&FMath::IsFinite(V.Z);} bool Near(FVector A,FVector B,float Radius){return FVector::Dist2D(A,B)<=Radius&&FMath::Abs(A.Z-B.Z)<=60;} bool Alive(AActor* A){return IsValid(A)&&!A->IsActorBeingDestroyed();} }
bool UOAGDNavigationComponent::Configure(float S,float A,float B,float D,float R){
    if(Busy()||Notifying)return false;
    for(float V:{S,A,B,D,R})if(!FMath::IsFinite(V)||V<=0)return false;
    if(S>2000||A>200||B>60||D>600||R<0.1f||R>5)return false;
    Speed=S;Arrival=A;Blocked=B;Deadline=D;RepathSeconds=R;return true;
}
bool UOAGDNavigationComponent::ReadyMap() const {
    auto* N=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    return N&&N->GetDefaultNavDataInstance(FNavigationSystem::DontCreate);
}
bool UOAGDNavigationComponent::Plan(FVector At){
    Path.Reset();Index=0;
    auto* N=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    if(!N||!ReadyMap()){LastError=TEXT("navigation_unavailable");return false;}
    FNavLocation Start,End;
    if(!N->ProjectPointToNavigation(At,Start,FVector(50,50,60))||!N->ProjectPointToNavigation(Goal,End,FVector(50,50,60))||!Near(At,Start.Location,50)||!Near(Goal,End.Location,50)){LastError=TEXT("outside_navigation");return false;}
    auto* P=UNavigationSystemV1::FindPathToLocationSynchronously(this,Start.Location,End.Location);
    if(!P||!P->IsValid()||P->IsPartial()||P->PathPoints.IsEmpty()||!Near(P->PathPoints.Last(),End.Location,10)){LastError=TEXT("unreachable");return false;}
    Path=P->PathPoints;return true;
}
bool UOAGDNavigationComponent::Request(const FString& RequestId,AActor* Mover,FVector Destination,AActor* Target,FVector FootOffset,FVector TargetOffset){
    LastError.Empty();
    if(Notifying||Busy()||Suspended){LastError=TEXT("busy_or_suspended");return false;}
    if(RequestId.IsEmpty()||RequestId.Len()>80||Seen.Contains(RequestId)){LastError=TEXT("invalid_or_duplicate_id");return false;}
    if(!Alive(Mover)||Mover->GetWorld()!=GetWorld()||!Finite(Destination)||!Finite(FootOffset)||!Finite(TargetOffset)){LastError=TEXT("invalid_request");return false;}
    if(Target&&(!Alive(Target)||Target->GetWorld()!=GetWorld())){LastError=TEXT("invalid_target");return false;}
    Goal=Target?Target->GetActorLocation()+TargetOffset:Destination;
    FVector At=Mover->GetActorLocation()+FootOffset;
    if(!Finite(At)||!Finite(Goal)){LastError=TEXT("invalid_position");return false;}
    if(!Plan(At))return false;
    Subject=Mover;TargetActor=Target;Tracking=Target!=nullptr;Offset=FootOffset;TargetOffsetValue=TargetOffset;Anchor=At;
    Elapsed=Stalled=Repath=0;DesiredVelocity=FVector::ZeroVector;Id=RequestId;Seen.Add(RequestId);if(Seen.Num()>256)Seen.RemoveAt(0);
    State=TEXT("moving");Reason.Empty();Emit(RequestId,TEXT("started"),TEXT(""));return true;
}
void UOAGDNavigationComponent::Step(float Delta){
    DesiredVelocity=FVector::ZeroVector;
    if(!Busy()||Suspended||Notifying)return;
    if(!FMath::IsFinite(Delta)||Delta<0){Finish(TEXT("failed"),TEXT("invalid_delta"));return;}
    if(!Alive(Subject.Get())){Finish(TEXT("failed"),TEXT("mover_lost"));return;}
    const FVector At=Subject->GetActorLocation()+Offset;
    if(!Finite(At)){Finish(TEXT("failed"),TEXT("invalid_position"));return;}
    if(Tracking){if(!Alive(TargetActor.Get())){Finish(TEXT("failed"),TEXT("target_lost"));return;}Goal=TargetActor->GetActorLocation()+TargetOffsetValue;if(!Finite(Goal)){Finish(TEXT("failed"),TEXT("invalid_target"));return;}}
    Elapsed+=Delta;Repath+=Delta;
    if(Elapsed>Deadline){Finish(TEXT("failed"),TEXT("timeout"));return;}
    if(Repath>=RepathSeconds){Repath=0;if(!Plan(At)){Finish(TEXT("failed"),LastError);return;}}
    if(Near(At,Goal,Arrival)){if(!Plan(At))Finish(TEXT("failed"),LastError);else Finish(TEXT("arrived"),TEXT(""));return;}
    if(FVector::Dist2D(At,Anchor)>=3){Anchor=At;Stalled=0;}else Stalled+=Delta;
    if(Stalled>=Blocked){Finish(TEXT("failed"),TEXT("blocked"));return;}
    while(Index<Path.Num()&&Near(At,Path[Index],20))++Index;
    if(Index>=Path.Num())return;
    FVector Difference=Path[Index]-At;Difference.Z=0;
    DesiredVelocity=Difference.GetSafeNormal()*FMath::Min(Speed,(float)Difference.Size()/FMath::Max(Delta,0.001f));
}
void UOAGDNavigationComponent::Emit(const FString& RequestId,const FString& Event,const FString& Why){
    const FString CopyId=RequestId,CopyEvent=Event,CopyReason=Why;bool Previous=Notifying;Notifying=true;Lifecycle.Broadcast(CopyId,CopyEvent,CopyReason);Notifying=Previous;
}
void UOAGDNavigationComponent::Finish(const FString& Result,const FString& Why){
    if(!Busy())return;const FString OldId=Id;Id.Empty();State=Result;Reason=Why;DesiredVelocity=FVector::ZeroVector;Path.Reset();Subject.Reset();TargetActor.Reset();Emit(OldId,State,Reason);
}
void UOAGDNavigationComponent::Cancel(const FString& Why){Finish(TEXT("cancelled"),Why);}
void UOAGDNavigationComponent::SetSuspended(bool Value){Suspended=Value;if(Value)Cancel(TEXT("suspended"));}
void UOAGDNavigationComponent::Clear(){Cancel(TEXT("cleared"));Seen.Reset();Path.Reset();DesiredVelocity=FVector::ZeroVector;State=TEXT("idle");Reason.Empty();}
void UOAGDNavigationComponent::EndPlay(const EEndPlayReason::Type Why){Clear();Super::EndPlay(Why);}
