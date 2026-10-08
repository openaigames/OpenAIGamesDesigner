#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimNotifies/AnimNotify.h"
#include "AnimNotify_ActionTiming.generated.h"

UCLASS(meta=(DisplayName="Record Action Event"))
class ACTIONTIMING_API UAnimNotify_ActionTiming : public UAnimNotify {
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Action Timing") FString Track=TEXT("animation");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Action Timing") FString EventName=TEXT("contact");
    virtual void Notify(USkeletalMeshComponent* MeshComp,UAnimSequenceBase* Animation,const FAnimNotifyEventReference& Reference) override;
};
