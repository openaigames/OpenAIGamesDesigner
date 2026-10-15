#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "InputKeyEventArgs.h"
#include "OAGDInput.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOAGDActionChanged,FName,Action,float,Value);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOAGDCaptureFinished,bool,Success,FString,Detail);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOAGDPauseChanged,bool,Paused);

struct FOAGDInputBinding {
    FString Context;
    TArray<FString> Keys;
    bool Rebindable=false;
};

// Optional single-local-player router. The owning project forwards native InputKey
// events and applies pause/context callbacks; no character or animation dependency.
UCLASS(ClassGroup=(OAGD),meta=(BlueprintSpawnableComponent))
class OAGDCORE_API UOAGDInputComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UOAGDInputComponent();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float Delta,ELevelTick Tick,FActorComponentTickFunction* Function) override;
    UFUNCTION(BlueprintCallable) bool LoadProfile(const FString& Path,FString& Error);
    bool Configure(const FString& Json,FString& Error);
    bool HandleInput(const FInputKeyEventArgs& Args);
    UFUNCTION(BlueprintCallable) bool Feed(const FString& Key,float Value);
    UFUNCTION(BlueprintPure) float Strength(FName Action) const;
    UFUNCTION(BlueprintPure) FString Binding(FName Action,int32 Slot=0) const;
    UFUNCTION(BlueprintCallable) bool SetContext(FName Value);
    UFUNCTION(BlueprintCallable) void SetPause(FName Reason,bool Active);
    UFUNCTION(BlueprintPure) bool IsPaused() const { return Pauses.Num()>0; }
    UFUNCTION(BlueprintCallable) bool Rebind(FName Action,int32 Slot,const FString& Key,FString& Error);
    UFUNCTION(BlueprintCallable) bool BeginCapture(FName Action,int32 Slot=0);
    UFUNCTION(BlueprintCallable) void CancelCapture();
    UFUNCTION(BlueprintCallable) void RestoreDefaults();
    UFUNCTION(BlueprintCallable) void FocusLost();
    UFUNCTION(BlueprintCallable) void DisconnectPad(int32 Device);
    UFUNCTION(BlueprintCallable) bool SavePreferences(const FString& FileName,FString& Error) const;
    UFUNCTION(BlueprintCallable) bool LoadPreferences(const FString& FileName,FString& Error);
    UPROPERTY(BlueprintReadOnly) FName Context=TEXT("game");
    UPROPERTY(BlueprintReadOnly) int32 SelectedPad=-1;
    UPROPERTY(BlueprintAssignable) FOAGDActionChanged ActionChanged;
    UPROPERTY(BlueprintAssignable) FOAGDCaptureFinished CaptureFinished;
    UPROPERTY(BlueprintAssignable) FOAGDPauseChanged PauseChanged;
    static bool Supported(const FString& Key);
private:
    TMap<FName,FOAGDInputBinding> Actions,Defaults;
    TMap<FString,float> Raw;
    TMap<FString,FString> ModifierSources;
    TSet<FString> Blocked;
    TMap<FName,float> Values;
    TSet<FName> Pauses;
    FName Capture;
    int32 CaptureSlot=0;
    float Deadzone=.2f,DefaultDeadzone=.2f;
    FString ProfileId;
    FDelegateHandle ConnectionHandle,DeactivateHandle;
    bool HadFocus=false;
    void Barrier();
    void Publish();
    bool FeedState(const FString& Key,float Value);
    static bool Parse(const FString& Text,FString& Id,float& Zone,TMap<FName,FOAGDInputBinding>& Out,FString& Error);
    static bool Validate(const TMap<FName,FOAGDInputBinding>& Data,FString& Error);
    static FString Token(FKey Key);
    static FString PreferencePath(const FString& Name);
};
