#include "SceneGame.h"
#include "ScenePassage.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"
#include "Components/StaticMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Camera/CameraActor.h"
#include "GameFramework/PlayerController.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/GameViewportClient.h"
#include "HighResScreenshot.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformMisc.h"
ASceneGame::ASceneGame(){PrimaryActorTick.bCanEverTick=true;DefaultPawnClass=nullptr;}
void ASceneGame::Check(bool V,const FString& N){Checks.Add(N);if(!V)Failures.Add(N);}
static FVector C(FVector P){return FVector(-P.Z,P.X,P.Y)*100;}
void ASceneGame::BeginPlay(){Super::BeginPlay();Start=FPlatformTime::Seconds();FParse::Value(FCommandLine::Get(),TEXT("SceneReport="),Report);FParse::Value(FCommandLine::Get(),TEXT("SceneView="),View);if(Report.IsEmpty())Report=FPaths::ProjectSavedDir()/TEXT("runtime.json");auto Cam=GetWorld()->SpawnActor<ACameraActor>();auto Eye=C(FVector(12,7,-10));auto Target=C(FVector(2,1,3));Cam->SetActorLocation(Eye);Cam->SetActorRotation((Target-Eye).Rotation());GetWorld()->GetFirstPlayerController()->SetViewTarget(Cam);}
void ASceneGame::Tick(float Delta){
 Super::Tick(Delta);++Frame;
 if(Checks.IsEmpty()&&Frame>=3){
  FString Text;FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("OAGDData/case.json")));TSharedPtr<FJsonObject> Spec;Check(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Spec),TEXT("portable case config"));
  TMap<FString,AStaticMeshActor*> Originals;TMap<FString,TMap<int32,AStaticMeshActor*>> Groups;TArray<AStaticMeshActor*> Proxies;
  for(TActorIterator<AStaticMeshActor> It(GetWorld());It;++It){FString Group;int32 Id=-1;for(FName Tag:It->Tags){auto S=Tag.ToString();if(S.StartsWith(TEXT("OAGD_ID_")))Originals.Add(S.Mid(8),*It);if(S.StartsWith(TEXT("Replacement_")))Group=S.Mid(12);if(S.StartsWith(TEXT("SourceNode_")))Id=FCString::Atoi(*S.Mid(11));}if(!Group.IsEmpty()&&Id>=0)Groups.FindOrAdd(Group).Add(Id,*It);if(It->ActorHasTag(TEXT("OAGD_PROXY")))Proxies.Add(*It);}
  for(const FString Name:{TEXT("DoorA"),TEXT("DoorB"),TEXT("RetainedBox"),TEXT("MeshBox"),TEXT("BuildingA"),TEXT("BuildingB")}){Check(Groups.Contains(Name),TEXT("replacement exists ")+Name);auto Old=Originals.FindRef(TEXT("Gray")+Name);Check(Old&&!Old->GetStaticMeshComponent()->IsVisible(),TEXT("graybox hidden ")+Name);}
  Check(Originals.Contains(TEXT("Unrelated"))&&FMath::Abs(Originals[TEXT("Unrelated")]->GetActorLocation().Y-1075)<.01,TEXT("manual unrelated edit preserved"));
  if(Spec&&Groups.Contains(TEXT("DoorA"))&&Groups.Contains(TEXT("DoorB"))&&Groups.Contains(TEXT("BuildingA"))&&Groups.Contains(TEXT("BuildingB"))){
   auto& DA=Groups[TEXT("DoorA")];auto& DB=Groups[TEXT("DoorB")];
   Check(DA[5]->GetStaticMeshComponent()->GetStaticMesh()==DB[5]->GetStaticMeshComponent()->GetStaticMesh(),TEXT("doors share geometry"));Check(Groups[TEXT("BuildingA")][25]->GetStaticMeshComponent()->GetStaticMesh()==Groups[TEXT("BuildingB")][25]->GetStaticMeshComponent()->GetStaticMesh(),TEXT("building instances share geometry"));
   auto Doors=Spec->GetArrayField(TEXT("doors"));
   auto Point=[](const TSharedPtr<FJsonObject>& D,FVector P){auto O=D->GetArrayField(TEXT("origin"));double Y=D->GetNumberField(TEXT("yaw")),S=D->GetNumberField(TEXT("scale"));return FVector(O[0]->AsNumber(),O[1]->AsNumber(),O[2]->AsNumber())+FVector(FMath::Cos(Y)*P.X+FMath::Sin(Y)*P.Z,P.Y,-FMath::Sin(Y)*P.X+FMath::Cos(Y)*P.Z)*S;};
   auto A=Doors[0]->AsObject();auto B=Doors[1]->AsObject();auto A0=Point(A,FVector(.6,1.05,-1.5)),A1=Point(A,FVector(.6,1.05,1.5)),B0=Point(B,FVector(.6,1.05,-1.5)),B1=Point(B,FVector(.6,1.05,1.5));
   auto Probe=[&](const FString& Name,FVector From,FVector To,double Radius,double Height,bool Expected){auto R=OAGDScene::Passage(GetWorld(),From,To,Radius,Height);Check(R.Valid&&R.Clear==Expected,Name);};
   Check(DA[0]->GetActorLocation().Equals(C(Point(A,FVector::ZeroVector)),.1),TEXT("planned root A"));Check(DB[0]->GetActorLocation().Equals(C(Point(B,FVector::ZeroVector)),.1),TEXT("planned root B"));
   Probe(TEXT("A closed"),A0,A1,.25,1.8,false);Probe(TEXT("B closed"),B0,B1,.25,1.8,false);
   AStaticMeshActor* Proxy=nullptr;for(auto P:Proxies)if(P->GetAttachParentActor()==DA[5])Proxy=P;Check(Proxy!=nullptr,TEXT("leaf collision attached"));
   if(Proxy){auto Local=Proxy->GetRootComponent()->GetRelativeTransform();Proxy->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);DA[4]->AddActorLocalRotation(FRotator(0,90,0));Probe(TEXT("detector catches orphaned collision"),A0,A1,.25,1.8,false);Proxy->AttachToActor(DA[5],FAttachmentTransformRules::KeepRelativeTransform);Proxy->GetRootComponent()->SetRelativeTransform(Local);}
   Probe(TEXT("A opens after collision recovery"),A0,A1,.25,1.8,true);Probe(TEXT("B independently closed"),B0,B1,.25,1.8,false);DB[4]->AddActorLocalRotation(FRotator(0,90,0));Probe(TEXT("rotated scaled B opens"),B0,B1,.25,1.8,true);Probe(TEXT("B rejects oversized capsule"),B0,B1,.75,1.8,false);
   Probe(TEXT("retained box collision"),FVector(-3,1.5,-2),FVector(-3,1.5,2),.15,.4,false);Probe(TEXT("triangle box collision"),FVector(4,.5,-5),FVector(4,.5,-1),.15,.6,false);Probe(TEXT("building A wall"),FVector(-20,1.05,10),FVector(-3,1.05,10),.25,1.8,false);Probe(TEXT("building B wall"),FVector(6,1.05,10),FVector(22,1.05,10),.25,1.8,false);Probe(TEXT("outside street"),FVector(0,1.05,-5),FVector(8,1.05,-5),.25,1.8,true);
   FActorSpawnParameters Spawn;Spawn.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;auto Character=GetWorld()->SpawnActor<ACharacter>(ACharacter::StaticClass(),C(A0),FRotator::ZeroRotator,Spawn);Character->GetCharacterMovement()->SetMovementMode(MOVE_None);Character->GetCapsuleComponent()->SetCapsuleSize(25,90);Character->GetCapsuleComponent()->SetCollisionProfileName(TEXT("Pawn"));TArray<FVector> Route={A1,FVector(2,1.05,2),B0,B1};for(int32 I=0;I<Route.Num();++I){FHitResult Hit;Character->AddActorWorldOffset(C(Route[I])-Character->GetActorLocation(),true,&Hit);Check(!Hit.bBlockingHit&&Character->GetActorLocation().Equals(C(Route[I]),1),FString::Printf(TEXT("continuous character route leg %d"),I));}Character->Destroy();
   DA[4]->AddActorLocalRotation(FRotator(0,-90,0));Probe(TEXT("A recloses"),A0,A1,.25,1.8,false);Probe(TEXT("B remains open after A closes"),B0,B1,.25,1.8,true);DA[4]->AddActorLocalRotation(FRotator(0,60,0));
  }
 }
 if(Frame<120||FPlatformTime::Seconds()-Start<7)return;
 if(!Captured&&!FParse::Param(FCommandLine::Get(),TEXT("nullrhi"))){FScreenshotRequest::RequestScreenshot(Report+TEXT(".png"),false,false);Captured=true;Frame=0;return;}
 auto Root=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> CC,FF;for(auto S:Checks)CC.Add(MakeShared<FJsonValueString>(S));for(auto S:Failures)FF.Add(MakeShared<FJsonValueString>(S));Root->SetArrayField(TEXT("checks"),CC);Root->SetArrayField(TEXT("failures"),FF);Root->SetStringField(TEXT("view"),View);FString Output;FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Output));FFileHelper::SaveStringToFile(Output,*Report);FPlatformMisc::RequestExitWithStatus(false,Failures.IsEmpty()?0:1);
}
