#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Engine/DataAsset.h"
#include "Components/ActorComponent.h"
#include "OAGDPlayback.generated.h"

USTRUCT(BlueprintType)
struct FOAGDMarker {
 GENERATED_BODY()
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FName Name;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) float AtSeconds=0;
};
USTRUCT(BlueprintType)
struct FOAGDClipBinding {
 GENERATED_BODY()
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FName Id;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) TObjectPtr<class UAnimSequence> Sequence;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool Loop=false;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FName MotionOwner=TEXT("controller");
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool ControllerOwned=true;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool LayerOnly=false;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) TArray<FOAGDMarker> Markers;
};
UCLASS(BlueprintType)
class OAGDPLAYBACK_API UOAGDPlaybackSet : public UDataAsset {
 GENERATED_BODY()
public:
 UPROPERTY(EditAnywhere,BlueprintReadWrite) TArray<FOAGDClipBinding> Clips;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FString Revision;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FString ConstraintsJson;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FName DefaultAction=TEXT("action");
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool RootMotionEnabled=false;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool LocomotionEnabled=false;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) float WalkSpeedMps=1;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) float RunSpeedMps=2.5;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool LayersEnabled=false;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FName UpperRoot;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) TArray<FName> UpperRequiredBones;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) TArray<FName> LowerExcludedBones;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) TArray<FName> LayerClips;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) float LayerFadeIn=.12f;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) float LayerFadeOut=.16f;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) float LayerReplace=.12f;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FOAGDPlaybackEvent,FName,Action,int32,Run,FName,Name);
UCLASS(ClassGroup=(OAGD),meta=(BlueprintSpawnableComponent))
class OAGDPLAYBACK_API UOAGDPlaybackComponent : public UActorComponent {
 GENERATED_BODY()
public:
 UPROPERTY(EditAnywhere,BlueprintReadWrite) TObjectPtr<UOAGDPlaybackSet> Bindings;
 UPROPERTY(BlueprintReadOnly) int32 StateIndex=0;
 UPROPERTY(BlueprintReadOnly) int32 Generation=0;
 UPROPERTY(BlueprintReadOnly) float PositionSeconds=0;
 UPROPERTY(BlueprintReadOnly) float Rate=1;
 UPROPERTY(BlueprintReadOnly) bool Finished=false;
 UPROPERTY(BlueprintReadOnly) float MoveWeight=0;
 UPROPERTY(BlueprintReadOnly) float RunWeight=0;
 UPROPERTY(BlueprintReadOnly) float CycleHz=0;
 UPROPERTY(BlueprintReadOnly) float WalkTime=0;
 UPROPERTY(BlueprintReadOnly) float RunTime=0;
 UFUNCTION(BlueprintCallable) bool SetLocomotionSpeed(float SpeedMps);
 UPROPERTY(BlueprintAssignable) FOAGDPlaybackEvent Marker;
 UPROPERTY(BlueprintAssignable) FOAGDPlaybackEvent Ended;
 UFUNCTION(BlueprintCallable) bool Validate() const;
 UFUNCTION(BlueprintCallable) bool Select(FName Action);
 UFUNCTION(BlueprintCallable) bool SetRate(float Value);
 UFUNCTION(BlueprintCallable) void Reset(FName Action);
 UFUNCTION(BlueprintPure) FName Current() const;
 void Sample(UAnimSequence* Sequence,float Time,float FirstStepSeconds);
private:
 bool Started=false;
 bool Changing=false;
 bool ObservedStart=false;
 TSet<FName> Fired;
};
// A real AnimBP derives from this class; its project-owned AnimGraph selects poses.
UCLASS(Transient,Blueprintable)
class OAGDPLAYBACK_API UOAGDPlaybackAnimInstance : public UAnimInstance {
 GENERATED_BODY()
public:
 UPROPERTY(BlueprintReadOnly,Category="Playback") int32 StateIndex=0;
 UPROPERTY(BlueprintReadOnly,Category="Playback") float PlaybackRate=1;
 UPROPERTY(BlueprintReadOnly,Category="Playback") float MoveWeight=0;
 UPROPERTY(BlueprintReadOnly,Category="Playback") float RunWeight=0;
 UPROPERTY(BlueprintReadOnly,Category="Playback") float WalkRate=0;
 UPROPERTY(BlueprintReadOnly,Category="Playback") float RunRate=0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") float UpperWeight=0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") float FullWeight=0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") float UpperMix=0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") float FullMix=0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") TObjectPtr<UAnimSequence> Upper0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") TObjectPtr<UAnimSequence> Upper1;
 UPROPERTY(BlueprintReadOnly,Category="Layers") TObjectPtr<UAnimSequence> Full0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") TObjectPtr<UAnimSequence> Full1;
 UPROPERTY(BlueprintReadOnly,Category="Layers") float UpperRate0=0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") float UpperRate1=0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") float FullRate0=0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") float FullRate1=0;
 UPROPERTY(BlueprintReadOnly,Category="Layers") bool UpperLoop0=false;
 UPROPERTY(BlueprintReadOnly,Category="Layers") bool UpperLoop1=false;
 UPROPERTY(BlueprintReadOnly,Category="Layers") bool FullLoop0=false;
 UPROPERTY(BlueprintReadOnly,Category="Layers") bool FullLoop1=false;
 virtual void NativeUpdateAnimation(float Delta) override;
 virtual void NativePostEvaluateAnimation() override;
private:
 int32 EvaluatedGeneration=INDEX_NONE;
 float EvaluationDelta=0;
 int32 InitializedRequest=INDEX_NONE;
 TMap<FName,int32> LayerInitialized;
 TMap<FName,int32> LayerEvaluated;
};
