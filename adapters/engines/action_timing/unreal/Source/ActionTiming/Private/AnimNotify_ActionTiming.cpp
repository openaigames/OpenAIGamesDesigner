#include "AnimNotify_ActionTiming.h"
#include "ActionEventRecorder.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"
void UAnimNotify_ActionTiming::Notify(USkeletalMeshComponent* MeshComp,UAnimSequenceBase* Animation,const FAnimNotifyEventReference& Reference) {
    Super::Notify(MeshComp,Animation,Reference);
    if(MeshComp && MeshComp->GetOwner()) if(auto* Recorder=MeshComp->GetOwner()->FindComponentByClass<UActionEventRecorder>()) Recorder->RecordEvent(Track,EventName);
}
