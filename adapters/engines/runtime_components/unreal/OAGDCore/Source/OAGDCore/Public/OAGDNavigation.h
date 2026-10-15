#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "OAGDNavigation.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FOAGDNavigationEvent,const FString&,RequestId,const FString&,State,const FString&,Reason);
// Emits ground velocity; the project applies it through a collision-aware motor.
UCLASS(ClassGroup=(OAGD),meta=(BlueprintSpawnableComponent))
class OAGDCORE_API UOAGDNavigationComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UPROPERTY(BlueprintReadOnly) FVector DesiredVelocity=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) FVector Goal=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) TArray<FVector> Path;
    UPROPERTY(BlueprintReadOnly) FString State=TEXT("idle");
    UPROPERTY(BlueprintReadOnly) FString Reason;
    UPROPERTY(BlueprintReadOnly) FString LastError;
    UPROPERTY(BlueprintReadOnly) bool Suspended=false;
    UPROPERTY(BlueprintAssignable) FOAGDNavigationEvent Lifecycle;
    UFUNCTION(BlueprintCallable) bool Configure(float SpeedCm=300,float ArrivalCm=35,float BlockedSeconds=1,float MaxSeconds=20,float RepathSeconds=0.5);
    UFUNCTION(BlueprintPure) bool Busy() const {return !Id.IsEmpty();}
    UFUNCTION(BlueprintPure) bool ReadyMap() const;
    UFUNCTION(BlueprintCallable) bool Request(const FString& RequestId,AActor* Mover,FVector Destination,AActor* Target=nullptr,FVector FootOffset=FVector::ZeroVector,FVector TargetOffset=FVector::ZeroVector);
    UFUNCTION(BlueprintCallable) void Step(float Delta);
    UFUNCTION(BlueprintCallable) void Cancel(const FString& Why=TEXT("cancelled"));
    UFUNCTION(BlueprintCallable) void SetSuspended(bool Value);
    UFUNCTION(BlueprintCallable) void Clear();
protected:
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
private:
    float Speed=300,Arrival=35,Blocked=1,Deadline=20,RepathSeconds=0.5;
    float Elapsed=0,Stalled=0,Repath=0;
    int32 Index=0;
    bool Tracking=false,Notifying=false;
    FString Id;
    TArray<FString> Seen;
    TWeakObjectPtr<AActor> Subject,TargetActor;
    FVector Offset=FVector::ZeroVector,TargetOffsetValue=FVector::ZeroVector,Anchor=FVector::ZeroVector;
    bool Plan(FVector At);
    void Finish(const FString& Result,const FString& Why);
    void Emit(const FString& RequestId,const FString& Event,const FString& Why);
};
