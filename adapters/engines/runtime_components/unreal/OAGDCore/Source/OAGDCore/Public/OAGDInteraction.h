#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "OAGDInteraction.generated.h"

USTRUCT(BlueprintType)
struct FOAGDInteractionOffer {
 GENERATED_BODY()
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool Allowed=true;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FString Reason;
};
UCLASS(Blueprintable,ClassGroup=(OAGD),meta=(BlueprintSpawnableComponent))
class OAGDCORE_API UOAGDInteractableComponent : public UActorComponent {
 GENERATED_BODY()
public:
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FString StableId;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FString Prompt=TEXT("Interact");
 UPROPERTY(EditAnywhere,BlueprintReadWrite) float HoldSeconds=0;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) bool Enabled=true;
 UPROPERTY(EditAnywhere,BlueprintReadWrite) FVector AnchorOffset=FVector::ZeroVector;
 UFUNCTION(BlueprintNativeEvent) FOAGDInteractionOffer Query(AActor* Requester);
 virtual FOAGDInteractionOffer Query_Implementation(AActor* Requester){return FOAGDInteractionOffer();}
 UFUNCTION(BlueprintNativeEvent) bool Execute(AActor* Requester);
 virtual bool Execute_Implementation(AActor* Requester){return false;}
 FVector Anchor()const;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FOAGDInteractionEvent,FString,Request,FString,Target,FString,State,FString,Reason);
UCLASS(ClassGroup=(OAGD),meta=(BlueprintSpawnableComponent))
class OAGDCORE_API UOAGDInteractionComponent : public UActorComponent {
 GENERATED_BODY()
public:
 UFUNCTION(BlueprintCallable) bool Configure(float DistanceCm,float HalfAngleDegrees);
 UFUNCTION(BlueprintCallable) bool RegisterTarget(UOAGDInteractableComponent* Target);
 UFUNCTION(BlueprintCallable) void UnregisterTarget(const FString& Id);
 UFUNCTION(BlueprintCallable) void UpdateQuery(AActor* Requester,FVector Origin,FVector Direction,float Delta);
 UFUNCTION(BlueprintCallable) bool Begin(const FString& Request);
 UFUNCTION(BlueprintCallable) bool Cancel(const FString& Reason=TEXT("released"));
 UFUNCTION(BlueprintCallable) void SetSuspended(bool Value);
 UFUNCTION(BlueprintCallable) void Clear();
 UFUNCTION(BlueprintPure) bool Holding()const{return !RequestId.IsEmpty();}
 UFUNCTION(BlueprintPure) FString FocusedId()const;
 UPROPERTY(BlueprintReadOnly) FString Prompt;
 UPROPERTY(BlueprintReadOnly) FString Reason;
 UPROPERTY(BlueprintReadOnly) FString LastError;
 UPROPERTY(BlueprintReadOnly) bool Allowed=false;
 UPROPERTY(BlueprintReadOnly) float Progress=0;
 UPROPERTY(BlueprintAssignable) FOAGDInteractionEvent Lifecycle;
 virtual void EndPlay(const EEndPlayReason::Type Reason)override;
private:
 float Range=300,HalfAngle=55,Elapsed=0,Duration=0;
 bool Suspended=false,HasView=false,Notifying=false,Committing=false;
 FVector Origin=FVector::ZeroVector,Direction=FVector::ForwardVector;
 TWeakObjectPtr<AActor> Actor;
 TWeakObjectPtr<UOAGDInteractableComponent> Focus,Pending;
 TMap<FString,TWeakObjectPtr<UOAGDInteractableComponent>> Targets;
 TArray<FString> Seen;FString RequestId,TargetId;
 bool ValidSpec(UOAGDInteractableComponent* Target)const;
 bool Visible(UOAGDInteractableComponent* Target)const;
 void Refresh();void SetFocus(UOAGDInteractableComponent* Target);void Finish();
 bool Reject(const TCHAR* Message);void Emit(const FString& Request,const FString& Target,const FString& State,const FString& Detail);
};
