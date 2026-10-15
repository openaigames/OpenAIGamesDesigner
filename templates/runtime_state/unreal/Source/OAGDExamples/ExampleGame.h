#pragma once
#include "CoreMinimal.h"
#include "OAGDComponents.h"
#include "OAGDInput.h"
#include "OAGDFocus.h"
#include "OAGDStore.h"
#include "OAGDScene.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/GameModeBase.h"
#include "ExampleGame.generated.h"
UCLASS()
class OAGDEXAMPLES_API AStatePlayer : public AOAGDCharacter {
 GENERATED_BODY()
public: AStatePlayer();virtual void Tick(float Delta) override;
};
UCLASS()
class OAGDEXAMPLES_API AExampleGame : public AGameModeBase {
 GENERATED_BODY()
public: AExampleGame();virtual void BeginPlay() override;
};
UCLASS()
class OAGDEXAMPLES_API AStateController : public APlayerController {
 GENERATED_BODY()
public:
 AStateController();virtual void BeginPlay() override;virtual void Tick(float Delta) override;virtual void EndPlay(const EEndPlayReason::Type Reason) override;
 virtual bool InputKey(const FInputKeyEventArgs& Args) override;
 UPROPERTY() TObjectPtr<UOAGDInputComponent> Router;
 UPROPERTY() TObjectPtr<UOAGDSceneComponent> Scenes;
 UFUNCTION() void OnAction(FName Action,float Value);
 UFUNCTION() void OnPause(bool Value);
 UFUNCTION() void OnPrepared(bool Success,FString Detail);
 UFUNCTION() void OnCompleted(bool Success,FString Detail);
 void OpenMenu();void CloseMenu();void Choose(int32 Index);void Select(int32 Index);
 bool MenuOpen=false,Busy=false;
private:
 TUniquePtr<FOAGDStore> Store;
 FString SaveRoot,Identity,Message,Notice,Report,TestPhase;
 TMap<FString,FString> ScenePaths;
 TSharedPtr<FJsonObject> State,Settings,Pending;
 TSharedPtr<class SWidget> UI;TSharedPtr<class SVerticalBox> Menu;
 TArray<TSharedPtr<class SButton>> Buttons;FOAGDFocusStack Focus;
 int32 Selection=0,Frame=0,Phase=0;bool Testing=false,Finished=false;
 double StartedAt=0;
 TArray<FString> Checks,Failures;
 TWeakObjectPtr<ULevelStreamingDynamic> Previous;
 void BuildUI();void TestStep();void Next(){++Phase;Frame=0;}
 void Check(bool Ok,const FString& Name);void Finish();
 bool Validate(const TSharedPtr<FJsonObject>& Data,FString& Error) const;
 TSharedPtr<FJsonObject> Snapshot() const;
 bool Transition(const TSharedPtr<FJsonObject>& Data,FString& Error);
 bool SaveGame(const FString& Slot,const TSharedPtr<FJsonObject>& Data,FString& Error);
 bool LoadGame(const FString& Slot,FString& Error);
 bool ApplySettings(const TSharedPtr<FJsonObject>& Data,FString& Error);
 AActor* Door(ULevelStreamingDynamic* Level,const FString& Scene) const;
 bool ApplyObjects(ULevelStreamingDynamic* Level,const TSharedPtr<FJsonObject>& Data,FString& Error);
 void Orbit(float Delta);
};
