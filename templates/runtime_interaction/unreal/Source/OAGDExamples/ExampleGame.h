#pragma once
#include "CoreMinimal.h"
#include "OAGDComponents.h"
#include "OAGDInput.h"
#include "OAGDFocus.h"
#include "OAGDInteraction.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/GameModeBase.h"
#include "ExampleGame.generated.h"
UCLASS()
class OAGDEXAMPLES_API UExampleTarget : public UOAGDInteractableComponent {
 GENERATED_BODY()
public:
 TWeakObjectPtr<class AExampleController> Rules;
 virtual FOAGDInteractionOffer Query_Implementation(AActor* Requester)override;
 virtual bool Execute_Implementation(AActor* Requester)override;
};
UCLASS()
class OAGDEXAMPLES_API AExampleProp : public AActor {
 GENERATED_BODY()
public:
 AExampleProp();
 UPROPERTY() TObjectPtr<class UStaticMeshComponent> Mesh;
 UPROPERTY() TObjectPtr<UExampleTarget> Target;
};
UCLASS()
class OAGDEXAMPLES_API AExamplePawn : public AOAGDCharacter {
 GENERATED_BODY()
public:AExamplePawn();virtual void Tick(float Delta)override;
};
UCLASS()
class OAGDEXAMPLES_API AExampleGame : public AGameModeBase {
 GENERATED_BODY()
public:AExampleGame();virtual void BeginPlay()override;
};
UCLASS()
class OAGDEXAMPLES_API AExampleController : public APlayerController {
 GENERATED_BODY()
public:
 AExampleController();virtual void BeginPlay()override;virtual void Tick(float Delta)override;virtual void EndPlay(const EEndPlayReason::Type Reason)override;
 virtual bool InputKey(const FInputKeyEventArgs& Args)override;
 UPROPERTY() TObjectPtr<UOAGDInputComponent> Router;
 UPROPERTY() TObjectPtr<UOAGDInteractionComponent> Interaction;
 UPROPERTY() TObjectPtr<AExampleProp> Door;
 UPROPERTY() TObjectPtr<AExampleProp> Pickup;
 UFUNCTION() void OnAction(FName Name,float Value);
 UFUNCTION() void OnPause(bool Value);
 UFUNCTION() void OnLifecycle(FString Request,FString Target,FString State,FString Reason);
 int32 Keys=0,Commits=0;bool DoorOpen=false,FailCommit=false,MenuOpen=false;
 FVector Aim=FVector::ForwardVector;
private:
 UPROPERTY() TArray<TObjectPtr<AActor>> Objects;
 UPROPERTY() TObjectPtr<AActor> Wall;
 TSharedPtr<SWidget> UI;TSharedPtr<class SVerticalBox> Menu;TArray<TSharedPtr<class SButton>> Buttons;FOAGDFocusStack Focus;
 FString Report,CallbackMode;bool CallbackRejected=false,Testing=false,Finished=false;
 int32 Selection=0,Serial=0,Generation=0,Phase=0,Frame=0;float DoorHold=.4f;
 double StartedAt=0,PhaseStart=0;
 TArray<FString> Checks,Failures;TArray<TSharedPtr<class FJsonValue>> Events;
 void BuildUI();void OpenMenu();void CloseMenu();void Choose(int32 Index);void ResetRoom();void Query(float Delta=0);
 AExampleProp* Prop(const FString& Id,FVector Position,FVector Size);
 AActor* Box(FVector Position,FVector Size);
 void TestStep();void Next(){++Phase;Frame=0;PhaseStart=FPlatformTime::Seconds();}
 void StartCase(const FString& Id);void Check(bool Ok,const FString& Name);void Finish();void Press(bool Down);
};
