#pragma once
#include "CoreMinimal.h"
#include "OAGDComponents.h"
#include "OAGDInput.h"
#include "OAGDNavigation.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/GameModeBase.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ExampleGame.generated.h"
UCLASS()
class OAGDEXAMPLES_API UExampleMapTools : public UBlueprintFunctionLibrary {
 GENERATED_BODY()
public: UFUNCTION(BlueprintCallable) static void CreateNavigationBounds(UObject* Context);
};
UCLASS()
class OAGDEXAMPLES_API AExamplePawn : public AOAGDCharacter {
 GENERATED_BODY()
public:
 AExamplePawn();virtual void Tick(float Delta)override;
 UPROPERTY() TObjectPtr<class UStaticMeshComponent> Body;
 bool IsNpc=false,Detectable=true;
 void Tint(FLinearColor Color);
};
UCLASS()
class OAGDEXAMPLES_API AExampleGame : public AGameModeBase {
 GENERATED_BODY()
public:AExampleGame();
};
UCLASS()
class OAGDEXAMPLES_API AExampleController : public APlayerController {
 GENERATED_BODY()
public:
 AExampleController();virtual void BeginPlay()override;virtual void Tick(float Delta)override;virtual void EndPlay(const EEndPlayReason::Type Reason)override;
 virtual bool InputKey(const FInputKeyEventArgs& Args)override;
 UPROPERTY() TObjectPtr<UOAGDInputComponent> Router;
 UPROPERTY() TObjectPtr<UOAGDNavigationComponent> Nav;
 UPROPERTY() TObjectPtr<AExamplePawn> Npc;
 UPROPERTY() TObjectPtr<AExamplePawn> Target;
 UFUNCTION() void OnAction(FName Name,float Value);
 UFUNCTION() void OnPause(bool Value);
 UFUNCTION() void OnLifecycle(const FString& Request,const FString& State,const FString& Reason);
private:
 UPROPERTY() TObjectPtr<AActor> Blocker;
 TSharedPtr<SWidget> UI;
 FString Report,Behavior=TEXT("stopped");
 bool Testing=false,Finished=false,Automatic=true,Frozen=false,CallbackMode=false,CallbackRejected=false;
 int32 Serial=0,Phase=0,PatrolIndex=0;
 float Speed=300,Radius=35,BlockedSeconds=1,Deadline=20,RepathSeconds=.5,Detection=600,LossSeconds=.6,SearchSeconds=.5,BehaviorClock=0,MaxDetour=0;
 FVector Home=FVector(-500,-300,0);TArray<FVector> PatrolPoints;
 double StartedAt=0,PhaseStart=0;
 TArray<FString> Checks,Failures,Transitions;TArray<TSharedPtr<class FJsonValue>> Events;
 void BuildUI();void Choose(int32 Index);void ToggleBlocker();void ResetNpc();
 void ChangeBehavior(const FString& Value);void BehaviorTick(float Delta);void BehaviorMove(FVector Goal,AActor* Follow=nullptr);bool VisibleTarget()const;
 void TestStep();void Next(){++Phase;PhaseStart=FPlatformTime::Seconds();}
 void StartCase(const FString& Id,FVector Goal=FVector(500,-300,0),AActor* Follow=nullptr);
 void Check(bool Ok,const FString& Name);void Finish();void Press(FKey Key,bool Down);
 AActor* Box(FVector Position,FVector Size);AExamplePawn* MakeNpc();
};
