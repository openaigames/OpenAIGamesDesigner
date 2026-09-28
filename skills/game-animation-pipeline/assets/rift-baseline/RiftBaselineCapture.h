#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "RiftBaselineCapture.generated.h"
class ARiftPlayer;class FJsonObject;class FJsonValue;
UCLASS()
class ARiftBaselineCapture : public AGameModeBase {
 GENERATED_BODY()
public:
 ARiftBaselineCapture();virtual void BeginPlay()override;virtual void Tick(float D)override;
 UPROPERTY() TObjectPtr<ARiftPlayer> Subject;
 int Clip=0,FrameIndex=0,Chain=0;float Settle=0,Duration=0;
 bool bRecording=false;
 FString Output;
 TSharedPtr<FJsonObject> Data,Current,Weapons;
 TArray<TSharedPtr<FJsonValue>> Clips,Frames;
};
