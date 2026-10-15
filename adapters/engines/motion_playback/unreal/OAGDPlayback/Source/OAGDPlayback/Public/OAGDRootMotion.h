#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "OAGDRootMotion.generated.h"
class ACharacter;class UOAGDPlaybackComponent;class UCharacterMovementComponent;
UCLASS(ClassGroup=(OAGD),meta=(BlueprintSpawnableComponent))
class OAGDPLAYBACK_API UOAGDRootMotionComponent : public UActorComponent {
 GENERATED_BODY()
public:
 UFUNCTION(BlueprintCallable) bool Configure(UOAGDPlaybackComponent* Player);
 UFUNCTION(BlueprintCallable) bool Start(FName Action,bool Restart=false);
 UFUNCTION(BlueprintCallable) void Cancel();
 // Call before project input and native CharacterMovement; never drive pose here.
 UFUNCTION(BlueprintCallable) void PrepareStep();
 UPROPERTY(BlueprintReadOnly) bool Active=false;
 UPROPERTY(BlueprintReadOnly) FVector RequestedWorldCm=FVector::ZeroVector;
 UPROPERTY(BlueprintReadOnly) int32 ExtractionCount=0;
 virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
 UPROPERTY() TObjectPtr<UOAGDPlaybackComponent> Playback;
 UPROPERTY() TObjectPtr<ACharacter> Character;
 void Flush();
 FTransform ObserveRoot(const FTransform& Transform,UCharacterMovementComponent* Movement,float Delta);
};
