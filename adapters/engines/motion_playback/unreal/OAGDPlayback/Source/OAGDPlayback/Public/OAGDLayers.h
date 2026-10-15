#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "OAGDLayers.generated.h"
class UAnimSequence;
class UOAGDPlaybackSet;
USTRUCT(BlueprintType)
struct FOAGDLayerState {
 GENERATED_BODY()
 UPROPERTY(BlueprintReadOnly) FName Action;
 UPROPERTY(BlueprintReadOnly) int32 Run=0;
 UPROPERTY(BlueprintReadOnly) bool Active=false;
 UPROPERTY(BlueprintReadOnly) int32 Bank=0;
 UPROPERTY(BlueprintReadOnly) float Mix=0;
 UPROPERTY(BlueprintReadOnly) float Weight=0;
 UPROPERTY(BlueprintReadOnly) float Target=0;
 UPROPERTY(BlueprintReadOnly) float Rate=1;
 UPROPERTY(BlueprintReadOnly) int32 Priority=0;
 UPROPERTY(BlueprintReadOnly) float PositionSeconds=0;
 UPROPERTY(BlueprintReadOnly) double TotalSeconds=0;
 bool First=true;
 UPROPERTY() TObjectPtr<UAnimSequence> Sequence0;
 UPROPERTY() TObjectPtr<UAnimSequence> Sequence1;
 float Rate0=0,Rate1=0;
 bool Loop0=false,Loop1=false;
 int32 BankRun0=0,BankRun1=0;
};
USTRUCT(BlueprintType)
struct FOAGDLayerEvent {
 GENERATED_BODY()
 UPROPERTY(BlueprintReadOnly) FName Channel;
 UPROPERTY(BlueprintReadOnly) FName Action;
 UPROPERTY(BlueprintReadOnly) int32 Run=0;
 UPROPERTY(BlueprintReadOnly) FName Kind;
 UPROPERTY(BlueprintReadOnly) FName Name;
 UPROPERTY(BlueprintReadOnly) int32 Cycle=0;
 UPROPERTY(BlueprintReadOnly) float AtSeconds=0;
 UPROPERTY(BlueprintReadOnly) float PositionSeconds=0;
 UPROPERTY(BlueprintReadOnly) double TotalSeconds=0;
 UPROPERTY(BlueprintReadOnly) float Weight=0;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOAGDLayerEventDelegate,const FOAGDLayerEvent&,Event);
UCLASS(ClassGroup=(OAGD),meta=(BlueprintSpawnableComponent))
class OAGDPLAYBACK_API UOAGDLayersComponent:public UActorComponent {
 GENERATED_BODY()
public:
 UPROPERTY(BlueprintReadOnly) TObjectPtr<UOAGDPlaybackSet> Bindings;
 UPROPERTY(BlueprintReadOnly) FOAGDLayerState Upper;
 UPROPERTY(BlueprintReadOnly) FOAGDLayerState Full;
 UPROPERTY(BlueprintReadOnly) FName Rejection;
 UPROPERTY(BlueprintReadOnly) int32 ClockFaults=0;
 UPROPERTY(BlueprintAssignable) FOAGDLayerEventDelegate Event;
 UFUNCTION(BlueprintCallable) bool Configure(UOAGDPlaybackSet* InBindings);
 UFUNCTION(BlueprintCallable) bool Play(FName Channel,FName Action,int32 Priority=0,float Weight=1,float Speed=1,bool Restart=true);
 UFUNCTION(BlueprintCallable) bool Cancel(FName Channel,FName Reason=TEXT("cancelled"));
 UFUNCTION(BlueprintCallable) bool SetLayerWeight(FName Channel,float Value);
 UFUNCTION(BlueprintCallable) bool SetLayerRate(FName Channel,float Value);
 UFUNCTION(BlueprintCallable) void ResetLayers();
 void AdvanceEnvelopes(float Delta);
 void Sample(FName Channel,int32 Bank,int32 Token,float Position,float NativeDelta);
 FOAGDLayerState* State(FName Channel);
private:
 bool Changing=false;
 void End(FName Channel,FName Reason);
 void Emit(FName Channel,FName Kind,FName Name,int32 Cycle,float At);
};
