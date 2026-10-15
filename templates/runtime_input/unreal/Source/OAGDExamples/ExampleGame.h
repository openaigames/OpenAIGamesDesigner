#pragma once
#include "CoreMinimal.h"
#include "OAGDComponents.h"
#include "OAGDInput.h"
#include "OAGDFocus.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/GameModeBase.h"
#include "ExampleGame.generated.h"

UCLASS()
class OAGDEXAMPLES_API AInputPlayer : public AOAGDCharacter {
 GENERATED_BODY()
public:
 AInputPlayer();
 virtual void Tick(float Delta) override;
};
UCLASS()
class OAGDEXAMPLES_API AExampleGame : public AGameModeBase {
 GENERATED_BODY()
public:
 AExampleGame();
 virtual void BeginPlay() override;
};
UCLASS()
class OAGDEXAMPLES_API AInputController : public APlayerController {
 GENERATED_BODY()
public:
 AInputController();
 virtual void BeginPlay() override;
 virtual void EndPlay(const EEndPlayReason::Type Reason) override;
 virtual void Tick(float Delta) override;
 virtual bool InputKey(const FInputKeyEventArgs& Args) override;
 UPROPERTY(VisibleAnywhere,BlueprintReadOnly) TObjectPtr<UOAGDInputComponent> Router;
 UFUNCTION() void OnAction(FName Action,float Value);
 UFUNCTION() void OnPause(bool Paused);
 UFUNCTION() void OnCapture(bool Success,FString Detail);
 void OpenMenu();void CloseMenu();void Choose(int32 Index);void Select(int32 Index);
 bool MenuOpen=false,Started=false;
 int32 Actions=0,Selection=0;
 FString Message;
private:
 TSharedPtr<class SWidget> UI;
 TSharedPtr<class SVerticalBox> Menu;
 TArray<TSharedPtr<class SButton>> Buttons;
 FOAGDFocusStack Focus;
 bool Testing=false,Finished=false;
 int32 Frame=0,Phase=0,Count=0;
 FVector Before;
 TArray<FString> Checks,Failures;
 FString Report,Preference;
 void BuildUI();void TestStep();void Check(bool Ok,const FString& Name);void Finish();
 void Key(FKey Key,bool Down);void Pad(float Value);void Next(){++Phase;Frame=0;}
};
