#pragma once
#include "CoreMinimal.h"
#include "OAGDComponents.h"
#include "OAGDNavigation.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/GameModeBase.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ExampleGame.generated.h"
UCLASS()
class OAGDEXAMPLES_API UExampleMapTools : public UBlueprintFunctionLibrary {
 GENERATED_BODY()
public: UFUNCTION(BlueprintCallable) static bool BuildGeneratedScene(UObject* Context);
};
UCLASS()
class OAGDEXAMPLES_API AExamplePawn : public AOAGDCharacter {
 GENERATED_BODY()
public: AExamplePawn();UPROPERTY() TObjectPtr<class UStaticMeshComponent> Body;
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
 UPROPERTY() TObjectPtr<UOAGDNavigationComponent> Nav;
 UPROPERTY() TObjectPtr<AExamplePawn> Npc;
 UPROPERTY() TObjectPtr<class ACameraActor> SceneCamera;
private:
 TSharedPtr<SWidget> UI;TSharedPtr<class FJsonObject> Scene,Agent;
 TArray<TSharedPtr<class FJsonValue>> Queries,Cases,Trace,Path;
 TArray<FString> Checks,Failures;
 FString Report;bool Testing=false,Finished=false,Accepted=false;
 int32 Selected=0,Serial=0,Phase=0;
 float HalfHeight=90,MinFoot=0,SampleClock=0;
 double Started=0,PhaseTime=0,CaseStart=0;
 void Select(int32 Index);bool StartRoute();void BuildUI();void TestStep();void InitialChecks();
 bool Projected(FVector Point)const;void Check(bool Ok,const FString& Name);void Finish();void RecordCase();
};
