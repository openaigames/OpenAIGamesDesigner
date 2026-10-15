#pragma once
#include "CoreMinimal.h"
#include "OAGDComponents.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "ExampleGame.generated.h"

UCLASS()
class OAGDEXAMPLES_API AExamplePlayer : public AOAGDCharacter {
    GENERATED_BODY()
public:
    AExamplePlayer();
    virtual void Tick(float Delta) override;
    virtual void SetupPlayerInputComponent(class UInputComponent* Input) override;
    void Forward(float Value);
    void Right(float Value);
    void LookX(float Value);
    void LookY(float Value);
    void Act();
    void Retry();
    void TryJump();
    FVector Facing=FVector::ForwardVector;
};

UCLASS()
class OAGDEXAMPLES_API AExampleGame : public AGameModeBase {
    GENERATED_BODY()
public:
    AExampleGame();
    virtual void BeginPlay() override;
    virtual void Tick(float Delta) override;
    UFUNCTION() void ResetRules(int32 Generation);
    void Act();
    void Damage(int32 Amount);
    UPROPERTY(VisibleAnywhere) TObjectPtr<UOAGDSessionComponent> Session;
    UPROPERTY() TObjectPtr<AActor> Target;
    UPROPERTY() TObjectPtr<AActor> Door;
    UPROPERTY() TObjectPtr<AExamplePlayer> Player;
    FString Scenario=TEXT("training");
    int32 TargetHP=3,PlayerHP=3;
    bool HasKey=false,DoorOpen=false;
private:
    TArray<AOAGDGeometry*> Generated;
    bool Testing=false;
    float Time=0,LastHit=-100,StageTime=0;
    int32 Stage=0,Assertions=0;
    TArray<FString> Failures,Checks;
    FVector Before;
    void Check(bool Condition,const FString& Name);
    void Next();
    void TestStep(float Delta);
    void Finish();
};

UCLASS()
class OAGDEXAMPLES_API AExampleHUD : public AHUD {
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};
