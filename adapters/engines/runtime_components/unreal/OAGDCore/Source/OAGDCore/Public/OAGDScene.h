#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "OAGDScene.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOAGDSceneResult,bool,Success,FString,Detail);
// Passive streamed chunks; player and UI remain in the persistent level.
UCLASS(ClassGroup=(OAGD),meta=(BlueprintSpawnableComponent))
class OAGDCORE_API UOAGDSceneComponent : public UActorComponent {
 GENERATED_BODY()
public:
 UOAGDSceneComponent();
 UFUNCTION(BlueprintCallable) bool Stage(const FString& Package,FString& Error);
 UFUNCTION(BlueprintCallable) bool Commit(FString& Error);
 UFUNCTION(BlueprintCallable) bool Cancel();
 UPROPERTY(BlueprintAssignable) FOAGDSceneResult Prepared;
 UPROPERTY(BlueprintAssignable) FOAGDSceneResult Completed;
 UPROPERTY(BlueprintReadOnly) TObjectPtr<class ULevelStreamingDynamic> Current;
 UPROPERTY(BlueprintReadOnly) TObjectPtr<class ULevelStreamingDynamic> Staged;
 UPROPERTY(BlueprintReadOnly) bool Ready=false;
 virtual void TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick) override;
 virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
 bool Committing=false;double Deadline=0;
 UFUNCTION() void Loaded();
 UFUNCTION() void Shown();
 void Discard();
};
