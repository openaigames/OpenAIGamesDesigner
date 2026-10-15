#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "SceneGame.generated.h"
UCLASS()
class OAGDEXAMPLES_API ASceneGame: public AGameModeBase {
 GENERATED_BODY()
public:
 ASceneGame();
 virtual void BeginPlay() override;
 virtual void Tick(float Delta) override;
private:
 void Check(bool Value,const FString& Name);
 TArray<FString> Checks,Failures;
 FString Report,View;
 double Start=0;
 int32 Frame=0;
 bool Captured=false;
};
