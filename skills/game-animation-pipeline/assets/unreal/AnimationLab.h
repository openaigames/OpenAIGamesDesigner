#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "AnimationLab.generated.h"
class USkeletalMeshComponent;class UProceduralMeshComponent;class USpringArmComponent;class UCameraComponent;class UAnimSequence;
class FJsonObject;class FJsonValue;

UCLASS()
class AAnimationLabPawn : public APawn {
 GENERATED_BODY()
public:
 AAnimationLabPawn();
 virtual void BeginPlay()override;
 virtual void Tick(float D)override;
 virtual void SetupPlayerInputComponent(UInputComponent* Input)override;
 void SelectClip(int Index);void Sample(float Time);void BuildWeapon();void SaveBinding();void ResetBinding();
 void RevertBinding(){EditedBindings.Remove(WeaponID);ResetBinding();}
 void Pause(){bPlaying=!bPlaying;}void Previous(){SelectClip(ClipIndex-1);}void Next(){SelectClip(ClipIndex+1);}
 void BackFrame();void ForwardFrame();void Slower(){Rate=FMath::Max(.125f,Rate*.5f);}void Faster(){Rate=FMath::Min(2.f,Rate*2.f);}
 void CameraView();void ToggleDebug(){bDebug=!bDebug;}void Edit(int Axis,float Direction);
 void XP(){Edit(0,1);}void XM(){Edit(0,-1);}void YP(){Edit(1,1);}void YM(){Edit(1,-1);}void ZP(){Edit(2,1);}void ZM(){Edit(2,-1);}
 UPROPERTY() TObjectPtr<USkeletalMeshComponent> Body;
 UPROPERTY() TObjectPtr<UProceduralMeshComponent> Weapon;
 UPROPERTY() TObjectPtr<USpringArmComponent> Boom;
 UPROPERTY() TObjectPtr<UCameraComponent> Camera;
 UPROPERTY() TObjectPtr<UAnimSequence> Sequence;
 TSharedPtr<FJsonObject> Manifest;
 TArray<TSharedPtr<FJsonValue>> Clips;
 FString ManifestPath,ClipID,WeaponID,Status;
 FTransform Binding;
 TMap<FString,FTransform> EditedBindings;
 float Time=0,Length=1,Rate=1,Contact=0;
 int ClipIndex=0,View=0;
 bool bPlaying=true,bDebug=true,bBindingValid=false;
};

UCLASS()
class AAnimationLabHUD : public AHUD {
 GENERATED_BODY()
public:virtual void DrawHUD()override;
};

UCLASS()
class AAnimationLabMode : public AGameModeBase {
 GENERATED_BODY()
public:
 AAnimationLabMode();virtual void BeginPlay()override;virtual void Tick(float D)override;
 FString AuditPath,SelfTestPath;int AuditClip=0,AuditFrame=0;
 TSharedPtr<FJsonObject> Audit;
 TArray<TSharedPtr<FJsonValue>> AuditClips,Frames;
 bool bShowcase=false;float ScreenClock=0;int ScreenStep=0;
};
