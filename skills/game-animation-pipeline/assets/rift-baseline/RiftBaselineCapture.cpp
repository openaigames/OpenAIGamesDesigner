#include "RiftBaselineCapture.h"
#include "RiftCombatant.h"
#include "RiftWeapon.h"
#include "AnimationLab.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "ProceduralMeshComponent.h"
#include "Engine/World.h"
#include "Json.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
namespace AnimationLabIO {
 TArray<TSharedPtr<FJsonValue>> Vec(FVector V);
 TSharedPtr<FJsonObject> Transform(FTransform T);
 TArray<TSharedPtr<FJsonValue>> Bones(USkeletalMeshComponent* M);
 TSharedPtr<FJsonObject> Frame(USkeletalMeshComponent* M,USceneComponent* W,float T,const FTransform& Space);
 bool Write(const FString& Path,const TSharedPtr<FJsonObject>& O);
}
using namespace AnimationLabIO;
ARiftBaselineCapture::ARiftBaselineCapture(){DefaultPawnClass=nullptr;PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickGroup=TG_PostUpdateWork;}
void ARiftBaselineCapture::BeginPlay(){
 Super::BeginPlay();FApp::SetUseFixedTimeStep(true);FApp::SetFixedDeltaTime(1.0/60.0);
 if(!FParse::Value(FCommandLine::Get(),TEXT("AnimationLabCapture="),Output))Output=FPaths::ProjectSavedDir()/TEXT("AnimationLab/baseline.json");
 Subject=GetWorld()->SpawnActor<ARiftPlayer>(FVector(0,0,91),FRotator::ZeroRotator);Subject->Rival=nullptr;Subject->GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);Subject->GetCharacterMovement()->DisableMovement();
 AddTickPrerequisiteActor(Subject);AddTickPrerequisiteComponent(Subject->GetMesh());AddTickPrerequisiteActor(Subject->WeaponVisual);
 Data=MakeShared<FJsonObject>();Weapons=MakeShared<FJsonObject>();Data->SetStringField(TEXT("schema"),TEXT("animlab.capture/1"));Data->SetStringField(TEXT("stage"),TEXT("runtime_baseline"));
 auto Space=MakeShared<FJsonObject>();Space->SetStringField(TEXT("units"),TEXT("cm"));Space->SetStringField(TEXT("axes"),TEXT("X-forward Y-right Z-up"));Space->SetStringField(TEXT("handedness"),TEXT("left"));Space->SetStringField(TEXT("origin"),TEXT("character_ground"));Data->SetObjectField(TEXT("space"),Space);
 auto B=Bones(Subject->GetMesh());for(auto& V:B){auto P=V->AsObject()->GetObjectField(TEXT("rest"))->GetArrayField(TEXT("p"));P[2]=MakeShared<FJsonValueNumber>(P[2]->AsNumber()+91);V->AsObject()->GetObjectField(TEXT("rest"))->SetArrayField(TEXT("p"),P);}Data->SetArrayField(TEXT("bones"),B);
}
void ARiftBaselineCapture::Tick(float D){
 Super::Tick(D);if(!Subject||Clip>=11)return;
 const ERiftWeapon W=Clip<4||Clip==8||Clip==9?ERiftWeapon::Sword:ERiftWeapon::Hammer;
 const int Attack=Clip<8?Clip%4:0;
 const FString WeaponName=W==ERiftWeapon::Sword?TEXT("sword"):TEXT("hammer");
 if(!bRecording){
  Subject->ResetAction();Subject->SelectWeapon(W);Settle+=D;if(Settle<.35f)return;
  const FString ID=Clip<8?WeaponName+(Attack<3?FString::Printf(TEXT("_light_%d"),Attack+1):TEXT("_heavy")):Clip==8?TEXT("sword_chain"):Clip==9?TEXT("sword_to_hammer"):TEXT("hammer_chain");
  if(!Weapons->HasField(WeaponName)){
   auto Weapon=MakeShared<FJsonObject>();Weapon->SetStringField(TEXT("bone"),TEXT("hand_r"));Weapon->SetObjectField(TEXT("binding"),Transform(Subject->WeaponVisual->GetActorTransform().GetRelativeTransform(Subject->GetMesh()->GetSocketTransform(TEXT("hand_r")))));
   auto Grips=MakeShared<FJsonObject>();Grips->SetArrayField(TEXT("right"),Vec(FVector(-8,0,0)));if(W==ERiftWeapon::Hammer)Grips->SetArrayField(TEXT("left"),Vec(FVector(16,0,0)));Weapon->SetObjectField(TEXT("grips"),Grips);
   Weapon->SetArrayField(TEXT("segment_a"),Vec(FVector(5,0,0)));Weapon->SetArrayField(TEXT("segment_b"),Vec(FVector(W==ERiftWeapon::Hammer?100:118,0,0)));Weapon->SetNumberField(TEXT("radius_cm"),W==ERiftWeapon::Hammer?18:3);
   TArray<TSharedPtr<FJsonValue>> Sections;auto* Mesh=Subject->WeaponVisual->Mesh.Get();
   for(int S=0;S<Mesh->GetNumSections();S++){auto* Sec=Mesh->GetProcMeshSection(S);auto O=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> Vert,Normals,Triangles;for(auto& V:Sec->ProcVertexBuffer){Vert.Add(MakeShared<FJsonValueArray>(Vec(V.Position)));Normals.Add(MakeShared<FJsonValueArray>(Vec(V.Normal)));}for(auto T:Sec->ProcIndexBuffer)Triangles.Add(MakeShared<FJsonValueNumber>(T));O->SetArrayField(TEXT("vertices"),Vert);O->SetArrayField(TEXT("normals"),Normals);O->SetArrayField(TEXT("triangles"),Triangles);Sections.Add(MakeShared<FJsonValueObject>(O));}Weapon->SetArrayField(TEXT("sections"),Sections);Weapons->SetObjectField(WeaponName,Weapon);
  }
  Current=MakeShared<FJsonObject>();Current->SetStringField(TEXT("id"),ID);Current->SetStringField(TEXT("weapon"),WeaponName);Current->SetStringField(TEXT("role"),TEXT("baseline"));Current->SetNumberField(TEXT("fps"),60);
  const auto Strike=RiftRules::WeaponStrike(static_cast<int>(W),Attack);auto Timing=MakeShared<FJsonObject>();Timing->SetNumberField(TEXT("contact_s"),Strike.HitAt);Timing->SetNumberField(TEXT("chain_s"),Strike.ChainAt);Timing->SetNumberField(TEXT("active_start_s"),Strike.HitAt);Timing->SetNumberField(TEXT("active_end_s"),Strike.HitAt+1.f/60);Current->SetObjectField(TEXT("timing"),Timing);Current->SetNumberField(TEXT("test_distance_cm"),Strike.Reach);
  Duration=Clip<8?Strike.Duration:Clip==8?1.4f:Clip==9?1.8f:2.6f;Current->SetNumberField(TEXT("duration_s"),Duration);
  Subject->BeginAttack(Attack);FrameIndex=0;Chain=0;bRecording=true;
 }
 const float T=FrameIndex/60.f;FTransform Ground(Subject->GetActorQuat(),Subject->GetActorLocation()-FVector(0,0,91));auto F=Frame(Subject->GetMesh(),Subject->WeaponVisual->Mesh,T,Ground);F->SetNumberField(TEXT("action_time"),Subject->StateTime);F->SetNumberField(TEXT("attack_index"),Subject->AttackIndex);F->SetStringField(TEXT("weapon_id"),Subject->VisibleWeapon()==ERiftWeapon::Hammer?TEXT("hammer"):TEXT("sword"));F->SetBoolField(TEXT("hit_committed"),Subject->bHitCommitted);Frames.Add(MakeShared<FJsonValueObject>(F));
 if(Clip>=8&&Subject->State==ERiftState::Attack&&Subject->StateTime>=Subject->Strike.ChainAt-.1f&&Chain<(Clip==9?1:2)&&Subject->BufferedAttack<0){
  if(Clip==9){Subject->SelectWeapon(ERiftWeapon::Hammer);Subject->HeavyAttack();}else Subject->LightAttack();Chain++;
 }
 FrameIndex++;if(T>=Duration){Current->SetArrayField(TEXT("frames"),Frames);Clips.Add(MakeShared<FJsonValueObject>(Current));Frames.Reset();bRecording=false;Clip++;Settle=0;Subject->ResetAction();
  UE_LOG(LogTemp,Display,TEXT("ANIMLAB_BASELINE clip=%s frames=%d"),*Current->GetStringField(TEXT("id")),FrameIndex);
  if(Clip>=11){Data->SetArrayField(TEXT("clips"),Clips);Data->SetObjectField(TEXT("weapons"),Weapons);const bool OK=Write(Output,Data);UE_LOG(LogTemp,Display,TEXT("ANIMLAB_BASELINE_COMPLETE clips=%d"),Clips.Num());FPlatformMisc::RequestExitWithStatus(false,OK?0:1);}
 }
}
