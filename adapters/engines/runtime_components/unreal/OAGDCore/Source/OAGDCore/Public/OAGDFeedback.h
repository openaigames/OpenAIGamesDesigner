#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "GameFramework/Actor.h"
#include "OAGDFeedback.generated.h"

UCLASS(Abstract,Blueprintable)
class OAGDCORE_API AOAGDFeedbackVisual : public AActor {
 GENERATED_BODY()
public:
 UFUNCTION(BlueprintNativeEvent) void Sample(float Age,float Strength,FLinearColor Color);
 virtual void Sample_Implementation(float Age,float Strength,FLinearColor Color) {}
};
USTRUCT(BlueprintType)
struct OAGDCORE_API FOAGDFeedbackCue {
 GENERATED_BODY()
 UPROPERTY(EditAnywhere,BlueprintReadWrite) TObjectPtr<class USoundBase> Sound;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) TSubclassOf<AOAGDFeedbackVisual> Visual;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool UI=false;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool Loop=false;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool Spatial=true;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool ReplaceOldest=false;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) int32 Limit=2;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) float Duration=.6f;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) float Volume=.25f;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) float Camera=0;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FLinearColor Color=FLinearColor::White;
};
USTRUCT()
struct FOAGDFeedbackInstance {
 GENERATED_BODY()
 FName Cue;FString Event,Scope;TWeakObjectPtr<AActor> Owner;bool HasOwner=false,Follow=false;
 FVector Offset=FVector::ZeroVector;float Age=0,Strength=1;
 UPROPERTY() TObjectPtr<class UAudioComponent> Audio;
 UPROPERTY() TObjectPtr<AOAGDFeedbackVisual> Visual;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FOAGDFeedbackEvent,int32,Handle,FString,Event,FName,Cue,FString,State);
UCLASS(ClassGroup=(OAGD),meta=(BlueprintSpawnableComponent))
class OAGDCORE_API UOAGDFeedbackComponent : public UActorComponent {
 GENERATED_BODY()
public:
 UOAGDFeedbackComponent();
 UFUNCTION(BlueprintCallable) bool Configure(const TMap<FName,FOAGDFeedbackCue>& Bindings,int32 Budget,FString& Error);
 UFUNCTION(BlueprintCallable) int32 Play(FName Cue,const FString& Event,AActor* Owner,FVector Position,bool Follow,const FString& Scope,float Intensity=1);
 UFUNCTION(BlueprintCallable) bool Stop(int32 Handle,const FString& Reason=TEXT("stopped"));
 UFUNCTION(BlueprintCallable) void StopScope(const FString& Scope);
 UFUNCTION(BlueprintCallable) void Clear();
 UFUNCTION(BlueprintCallable) void SetGamePaused(bool Value);
 UPROPERTY(BlueprintReadOnly) FRotator CameraOffset=FRotator::ZeroRotator;
 UPROPERTY(BlueprintReadOnly) FString LastError;
 UPROPERTY(BlueprintAssignable) FOAGDFeedbackEvent Lifecycle;
 UPROPERTY() TMap<int32,FOAGDFeedbackInstance> Active;
 UPROPERTY() TMap<FName,FOAGDFeedbackCue> Cues;
 virtual void TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick) override;
 virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
 double LastWall=0;int32 Next=0,MaxActive=8;bool GamePaused=false,Emitting=false;TArray<FString> Seen;
 void Emit(int32 Handle,const FString& Event,FName Cue,const FString& State);
 int32 Reject(const TCHAR* Error);void RecomputeCamera();
};
