#pragma once
#include "CoreMinimal.h"
#include "OAGDComponents.h"
#include "OAGDPlayback.h"
#include "OAGDConstraints.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "Dom/JsonObject.h"
#include "ConstraintsGame.generated.h"
UCLASS()
class MOTIONPLAY_API AConstraintsPlayer:public AOAGDCharacter {
 GENERATED_BODY()
public:
 AConstraintsPlayer();virtual void BeginPlay() override;virtual void Tick(float Delta) override;
 virtual void EndPlay(const EEndPlayReason::Type Reason) override;virtual void SetupPlayerInputComponent(UInputComponent* Input) override;
 UPROPERTY() TObjectPtr<UOAGDPlaybackComponent> Motion;
 UPROPERTY() TObjectPtr<UOAGDConstraintsComponent> IK;
 UPROPERTY() TObjectPtr<class AStaticMeshActor> Floor;
 UPROPERTY() TObjectPtr<class AStaticMeshActor> Platform;
 UPROPERTY() TObjectPtr<class AStaticMeshActor> Prop;
 void Forward(float V);void Right(float V);void PickUp();void Drop();void Hop();void Take(bool Both=true);
 void NextCase();FString CaseName()const;void Observe(UWorld* World,ELevelTick Type,float Delta);
 FString Output,FramesDirectory,View=TEXT("game");float Clock=0;int32 CaseIndex=-1,FrameIndex=0;
 FVector2D Wish=FVector2D::ZeroVector;TSet<FString> Steps;TArray<TSharedPtr<FJsonValue>> Frames,Events;FDelegateHandle Observer;
 FOAGDConstraintSettings Original;
};
UCLASS()
class MOTIONPLAY_API AConstraintsGame:public AGameModeBase {GENERATED_BODY() public:AConstraintsGame();virtual void BeginPlay() override;};
UCLASS()
class MOTIONPLAY_API AConstraintsHUD:public AHUD {GENERATED_BODY() public:virtual void DrawHUD() override;};
