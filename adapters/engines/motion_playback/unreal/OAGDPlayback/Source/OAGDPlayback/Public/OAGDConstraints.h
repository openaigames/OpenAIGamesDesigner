#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Animation/AnimNodeBase.h"
#include "OAGDConstraints.generated.h"

// Snapshot is copied on the game thread. Evaluate never queries a world or UObject.
struct FOAGDConstraintSettings {
 bool Feet=false,Grip=false;FName Pelvis,Main;TArray<FName> Left,Right,Offhand;
 float Sole=7,ProbeUp=45,ProbeDown=50,MaxStep=25,MaxSlope=35,MaxPelvis=20,FeetBlend=.15f,GripBlend=.15f;
 FVector Knee=FVector(1,0,0),Elbow=FVector(0,-1,-.3);FTransform MainSocket,SupportSocket;
};
struct FOAGDConstraintInput {
 bool Valid=false,Grounded=true,Holding=false,TwoHanded=false,Contact=false;
 float Delta=0;FVector2D Contacts=FVector2D(1,1);FTransform Mesh,Actor;
 bool Hit[2]={false,false};FVector Point[2],Normal[2];FOAGDConstraintSettings Settings;
};
struct FOAGDConstraintResult {
 FVector2D Weights=FVector2D::ZeroVector;float GripWeight=0,Pelvis=0;
 FString FeetStatus[2]={TEXT("disabled"),TEXT("disabled")},GripStatus=TEXT("released");
 FVector Goals[2];FTransform Support;
};
UCLASS(ClassGroup=(OAGD),meta=(BlueprintSpawnableComponent))
class OAGDPLAYBACK_API UOAGDConstraintsComponent:public UActorComponent {
 GENERATED_BODY()
public:
 UFUNCTION(BlueprintCallable) bool Configure(class USkeletalMeshComponent* Target,const FString& Json);
 UFUNCTION(BlueprintCallable) void Prepare(float Delta,bool Grounded,FVector2D Contacts,bool SupportContact);
 UFUNCTION(BlueprintCallable) bool Take(class USceneComponent* Target,bool Both=true);
 UFUNCTION(BlueprintCallable) void Release();
 UFUNCTION(BlueprintCallable) void Reset();
 virtual void EndPlay(const EEndPlayReason::Type Reason) override;
 FOAGDConstraintInput Snapshot() const;void Finalized();
 FOAGDConstraintSettings Settings;FOAGDConstraintResult Result;
 bool Valid=false,Holding=false,TwoHanded=false,Contact=false,Grounded=true;float Delta=0;
 FVector2D Contacts=FVector2D(1,1);int32 ResetGeneration=0,GripGeneration=0;
 UPROPERTY() TObjectPtr<USkeletalMeshComponent> Mesh;
 UPROPERTY() TObjectPtr<USceneComponent> Prop;
private:FDelegateHandle FinalizeHandle;
};
USTRUCT(BlueprintInternalUseOnly)
struct OAGDPLAYBACK_API FAnimNode_OAGDConstraints:public FAnimNode_Base {
 GENERATED_BODY()
 UPROPERTY(EditAnywhere,BlueprintReadWrite,Category=Links) FPoseLink Source;
 virtual void Initialize_AnyThread(const FAnimationInitializeContext& Context) override;
 virtual void CacheBones_AnyThread(const FAnimationCacheBonesContext& Context) override;
 virtual void Update_AnyThread(const FAnimationUpdateContext& Context) override;
 virtual void Evaluate_AnyThread(FPoseContext& Output) override;
 virtual bool HasPreUpdate()const override{return true;}
 virtual void PreUpdate(const UAnimInstance* Instance) override;
 FOAGDConstraintInput Input;FOAGDConstraintResult Result;int32 ResetGeneration=-1,GripGeneration=-1;
};
