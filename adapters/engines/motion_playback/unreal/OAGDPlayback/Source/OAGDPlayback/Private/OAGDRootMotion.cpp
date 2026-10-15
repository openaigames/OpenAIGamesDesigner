#include "OAGDRootMotion.h"
#include "OAGDPlayback.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
bool UOAGDRootMotionComponent::Configure(UOAGDPlaybackComponent* Player){
 auto* C=Cast<ACharacter>(GetOwner());
 if(!C||!Player||Player->GetOwner()!=C||!Player->Validate()||!Player->Bindings->RootMotionEnabled)return false;
 auto* M=C->GetCharacterMovement();
 if(M->ProcessRootMotionPostConvertToWorld.IsBound())return false; // do not steal another consumer
 Playback=Player;Character=C;M->ProcessRootMotionPostConvertToWorld.BindUObject(this,&UOAGDRootMotionComponent::ObserveRoot);
 if(auto* Anim=C->GetMesh()->GetAnimInstance())Anim->SetRootMotionMode(ERootMotionMode::RootMotionFromEverything);
 return true;
}
void UOAGDRootMotionComponent::Flush(){
 Character->ConsumeMovementInputVector();
 auto* M=Character->GetCharacterMovement();M->StopMovementImmediately();M->RootMotionParams.Clear();
 if(auto* Anim=Character->GetMesh()->GetAnimInstance())Anim->ConsumeExtractedRootMotion(1.f);
 RequestedWorldCm=FVector::ZeroVector;
}
bool UOAGDRootMotionComponent::Start(FName Action,bool Restart){
 if(!Playback||!Character||!Playback->Validate())return false;
 const auto* B=Playback->Bindings->Clips.FindByPredicate([Action](const auto& C){return C.Id==Action;});
 if(!B||B->MotionOwner!=TEXT("animation")||Character->GetCharacterMovement()->IsFalling())return false;
 if(Active&&Playback->Current()==Action&&!Restart)return true;
 Flush();
 if(Restart)Playback->Reset(Action);else if(!Playback->Select(Action))return false;
 Active=true;return true;
}
void UOAGDRootMotionComponent::Cancel(){
 if(!Playback||!Character)return;
 Active=false;Flush();Playback->Reset(TEXT("idle"));
}
void UOAGDRootMotionComponent::PrepareStep(){
 RequestedWorldCm=FVector::ZeroVector;ExtractionCount=0;
 if(!Playback)return;
 const auto* B=Playback->Bindings->Clips.FindByPredicate([this](const auto& C){return C.Id==Playback->Current();});
 if(Active&&(Playback->Finished||!B||B->MotionOwner!=TEXT("animation")))Cancel();
 if(Active)Character->ConsumeMovementInputVector();
}
FTransform UOAGDRootMotionComponent::ObserveRoot(const FTransform& Transform,UCharacterMovementComponent* Movement,float Delta){
 // CharacterMovement has extracted and converted the actual graph output.
 // Return it to native collision movement; never separately translate the actor.
 if(!Active)return FTransform::Identity;
 FVector Translation=Transform.GetTranslation();Translation.Z=0;
 RequestedWorldCm+=Translation;++ExtractionCount;
 return FTransform(FQuat::Identity,Translation);
}
void UOAGDRootMotionComponent::EndPlay(const EEndPlayReason::Type Reason){
 if(Character&&Character->GetCharacterMovement()->ProcessRootMotionPostConvertToWorld.IsBoundToObject(this))Character->GetCharacterMovement()->ProcessRootMotionPostConvertToWorld.Unbind();
 Super::EndPlay(Reason);
}
