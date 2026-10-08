#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ActionEventRecorder.generated.h"

UCLASS(ClassGroup=(Debugging), meta=(BlueprintSpawnableComponent))
class ACTIONTIMING_API UActionEventRecorder : public UActorComponent {
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Action Timing")
    bool StartRecording(const FString& Action, const FString& Revision, const FString& Source, const FString& InputMode, const FString& InputDescription);
    UFUNCTION(BlueprintCallable, Category="Action Timing")
    bool RecordEvent(const FString& Track, const FString& EventName, double UncertaintySeconds = 0.0);
    UFUNCTION(BlueprintCallable, Category="Action Timing")
    FString StopAndSave(bool Complete = true);
    UFUNCTION(BlueprintPure, Category="Action Timing")
    bool IsRecording() const { return Active; }
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    bool Active = false;
    double StartSeconds = 0;
    int32 Dropped = 0;
    FString ActionName, BuildRevision, CaptureSource, Mode, Input, LastPath;
    struct FEvent { FString Track, Id; double Time, Uncertainty; };
    TArray<FEvent> Events;
    TMap<FString, int32> Counts;
};
