#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "OAGDMotionCapture.generated.h"
class USkeletalMeshComponent;
class UAnimSequence;
class FJsonValue;
UCLASS()
class OAGDMOTION_API AOAGDMotionCapture : public AGameModeBase {
    GENERATED_BODY()
public:
    AOAGDMotionCapture();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
private:
    UPROPERTY() TObjectPtr<USkeletalMeshComponent> Mesh;
    UPROPERTY() TObjectPtr<UAnimSequence> Animation;
    int32 SampleIndex=0, SampleCount=0;
    double SampleRate=30;
    FString ReportPath;
    TArray<TSharedPtr<FJsonValue>> Samples;
    bool Finished=false;
    void Finish(const FString& Error);
};
