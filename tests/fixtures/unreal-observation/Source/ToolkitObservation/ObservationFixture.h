#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/HUD.h"
#include "Curves/CurveFloat.h"
#include "ObservationFixture.generated.h"

// Native author source. JSON methods are bounded exchange interfaces, not storage.
UCLASS(BlueprintType)
class TOOLKITOBSERVATION_API UObservationSettings : public UDataAsset {
    GENERATED_BODY()
public:
    UObservationSettings();
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float WalkSpeed = 180.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Windup = .12f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float CleanupDelay = .075f;
    UPROPERTY(EditAnywhere, Instanced) TObjectPtr<UCurveFloat> DamageCurve;
    UFUNCTION(BlueprintCallable) FString ExportAuthorData() const;
    UFUNCTION(BlueprintCallable) bool ApplyAuthorData(const FString& Patch);
};

UCLASS()
class TOOLKITOBSERVATION_API AObservationPawn : public APawn {
    GENERATED_BODY()
public:
    AObservationPawn();
    virtual void BeginPlay() override;
    virtual void Tick(float Delta) override;
    virtual void SetupPlayerInputComponent(class UInputComponent* Input) override;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TObjectPtr<UObservationSettings> Settings;
    UPROPERTY(VisibleAnywhere) TObjectPtr<class UCapsuleComponent> Capsule;
    UPROPERTY(VisibleAnywhere) TObjectPtr<class UStaticMeshComponent> Body;
    UPROPERTY(VisibleAnywhere) TObjectPtr<class USceneComponent> GripAnchor;
    UPROPERTY(VisibleAnywhere) TObjectPtr<class UFloatingPawnMovement> Movement;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) float AppliedWalkSpeed = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) float AppliedDamage = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool EffectActive = false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) FString ActionState = TEXT("idle");
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) float TargetHealth = 42.f;
    UFUNCTION(BlueprintCallable) void Attack();
    UFUNCTION(BlueprintCallable) void Cancel();
    UFUNCTION(BlueprintCallable) void SetTravel(float X, float Y);
    UFUNCTION(BlueprintCallable) void RestartEncounter();
    UFUNCTION(BlueprintCallable) FString ExportObservationEvents() const;
private:
    TObjectPtr<class UStaticMeshComponent> RuntimeWeapon;
    float PhaseTime = 0;
    float CleanupRemaining = -1;
    FVector Travel = FVector::ZeroVector;
    FTransform StartingTransform;
    TArray<TSharedPtr<class FJsonValue>> Events;
    void Mark(const FString& Event, const FString& Detail = TEXT(""));
    void FinishCleanup();
    void Forward(){SetTravel(1,0);}
    void Back(){SetTravel(-1,0);}
    void Stop(){SetTravel(0,0);}
};

UCLASS()
class TOOLKITOBSERVATION_API AObservationHUD : public AHUD {
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};
