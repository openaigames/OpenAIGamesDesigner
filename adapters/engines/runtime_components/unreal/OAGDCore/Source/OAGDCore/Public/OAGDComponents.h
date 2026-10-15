#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/Actor.h"
#include "Components/ActorComponent.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OAGDComponents.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOAGDRestarted, int32, Generation);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOAGDStateChanged, FName, State);

// Optional character base. Input bindings and game rules are always project-owned.
UCLASS(Blueprintable)
class OAGDCORE_API AOAGDCharacter : public ACharacter {
    GENERATED_BODY()
public:
    AOAGDCharacter();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<class USpringArmComponent> CameraArm;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<class UCameraComponent> FollowCamera;
    UFUNCTION(BlueprintCallable) void MoveWorld(FVector2D Wish);
    UFUNCTION(BlueprintCallable) void Orbit(FVector2D Delta);
    UFUNCTION(BlueprintCallable) void ResetMotor(FVector Position);
};

UCLASS(ClassGroup=(OAGD), meta=(BlueprintSpawnableComponent))
class OAGDCORE_API UOAGDSessionComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UPROPERTY(BlueprintReadOnly) FName State = TEXT("playing");
    UPROPERTY(BlueprintReadOnly) int32 Generation = 0;
    UPROPERTY(BlueprintAssignable) FOAGDRestarted Restarted;
    UPROPERTY(BlueprintAssignable) FOAGDStateChanged StateChanged;
    UFUNCTION(BlueprintCallable) void SetState(FName Value);
    UFUNCTION(BlueprintCallable) void Restart();
};

UCLASS()
class OAGDCORE_API UOAGDQuery : public UBlueprintFunctionLibrary {
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, meta=(WorldContext="Context"))
    static bool VisibleHit(UObject* Context, FVector Origin, FVector Direction, float Distance, AActor* Ignore, FHitResult& Hit);
};

// Optional procedural scene consumer. One actor per stable mesh ID for replacement.
UCLASS(Blueprintable)
class OAGDCORE_API AOAGDGeometry : public AActor {
    GENERATED_BODY()
public:
    AOAGDGeometry();
    UPROPERTY(VisibleAnywhere) TObjectPtr<class UProceduralMeshComponent> Geometry;
    static bool LoadScene(UWorld* World, const FString& AbsolutePath, TArray<AOAGDGeometry*>& Out, FString& Error);
};
