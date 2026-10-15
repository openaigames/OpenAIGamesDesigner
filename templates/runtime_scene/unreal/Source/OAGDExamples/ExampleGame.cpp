#include "ExampleGame.h"
#include "Components/StaticMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "UObject/ConstructorHelpers.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/EngineVersion.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"
#include "UnrealClient.h"
#include "Modules/ModuleManager.h"
#include "NavigationSystem.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "ProceduralMeshComponent.h"
#if WITH_EDITOR
#include "Builders/CubeBuilder.h"
#include "ActorFactories/ActorFactory.h"
#endif
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl,OAGDExamples,"OAGDExamples");
static FString SceneFile(){return FPaths::ProjectContentDir()/TEXT("generated/scene/scene.json");}
static TSharedPtr<FJsonObject> ReadScene(){FString Text;TSharedPtr<FJsonObject> Doc;FFileHelper::LoadFileToString(Text,*SceneFile());FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Doc);return Doc;}
static FVector V(const TArray<TSharedPtr<FJsonValue>>& A){return FVector(-A[2]->AsNumber(),A[0]->AsNumber(),A[1]->AsNumber())*100;}
static TArray<TSharedPtr<FJsonValue>> ToSource(FVector P){return {MakeShared<FJsonValueNumber>(P.Y/100),MakeShared<FJsonValueNumber>(P.Z/100),MakeShared<FJsonValueNumber>(-P.X/100)};}
bool UExampleMapTools::BuildGeneratedScene(UObject* Context){
#if WITH_EDITOR
 UWorld* World=Cast<UWorld>(Context);if(!World&&Context)World=Context->GetWorld();if(!World)return false;
 for(TActorIterator<AOAGDGeometry> It(World);It;++It)return false; // Never overwrite an edited generated map.
 TArray<AOAGDGeometry*> Objects;FString Error;if(!AOAGDGeometry::LoadScene(World,SceneFile(),Objects,Error)){UE_LOG(LogTemp,Error,TEXT("%s"),*Error);return false;}
 FBox Bounds(ForceInit);auto* Material=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Scene/Vertex.Vertex"));
 for(auto* A:Objects){A->Geometry->SetMobility(EComponentMobility::Static);A->Geometry->SetCanEverAffectNavigation(true);if(Material)A->Geometry->SetMaterial(0,Material);Bounds+=A->Geometry->Bounds.GetBox();}
 Bounds=Bounds.ExpandBy(200);auto* Volume=World->SpawnActor<ANavMeshBoundsVolume>(Bounds.GetCenter(),FRotator::ZeroRotator);
 auto* Builder=NewObject<UCubeBuilder>();Builder->X=Bounds.GetSize().X;Builder->Y=Bounds.GetSize().Y;Builder->Z=Bounds.GetSize().Z;UActorFactory::CreateBrushForVolumeActor(Volume,Builder);
 if(auto* N=FNavigationSystem::GetCurrent<UNavigationSystemV1>(World)){
  N->OnNavigationBoundsUpdated(Volume);N->Build();
  auto Spec=ReadScene();auto Agent=Spec->GetObjectField(TEXT("navigation"))->GetObjectField(TEXT("agent"));
  if(auto* Recast=Cast<ARecastNavMesh>(N->GetDefaultNavDataInstance(FNavigationSystem::Create))){
   Recast->AgentRadius=Agent->GetNumberField(TEXT("navigation_radius_m"))*100;Recast->AgentHeight=Agent->GetNumberField(TEXT("navigation_height_m"))*100;Recast->AgentMaxSlope=Agent->GetNumberField(TEXT("max_slope_degrees"));
   for(auto& R:Recast->NavMeshResolutionParams){R.CellSize=10;R.CellHeight=5;R.AgentMaxStepHeight=Agent->GetNumberField(TEXT("max_step_m"))*100;}
   auto Config=Recast->GetConfig();Config.AgentRadius=Recast->AgentRadius;Config.AgentHeight=Recast->AgentHeight;Recast->SetConfig(Config);N->Build();
  }
 }
 return true;
#else
 return false;
#endif
}
AExamplePawn::AExamplePawn(){Body=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));Body->SetupAttachment(RootComponent);static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));Body->SetStaticMesh(Sphere.Object);Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);Body->SetCanEverAffectNavigation(false);GetCapsuleComponent()->SetCanEverAffectNavigation(false);GetCharacterMovement()->bRunPhysicsWithNoController=true;GetCharacterMovement()->MaxWalkSpeed=300;}
AExampleGame::AExampleGame(){DefaultPawnClass=nullptr;PlayerControllerClass=AExampleController::StaticClass();}
AExampleController::AExampleController(){Nav=CreateDefaultSubobject<UOAGDNavigationComponent>(TEXT("Navigation"));PrimaryActorTick.bCanEverTick=true;bAutoManageActiveCameraTarget=false;}
void AExampleController::BeginPlay(){Super::BeginPlay();Started=PhaseTime=FPlatformTime::Seconds();Testing=FParse::Param(FCommandLine::Get(),TEXT("OAGDSelfTest"));Report=FPaths::ProjectSavedDir()/TEXT("scene.json");FParse::Value(FCommandLine::Get(),TEXT("SceneReport="),Report);
 Scene=ReadScene();if(!Scene.IsValid()||!Scene->HasField(TEXT("navigation"))){Check(false,TEXT("generated scene metadata exists"));Finish();return;}
 auto Navigation=Scene->GetObjectField(TEXT("navigation"));Agent=Navigation->GetObjectField(TEXT("agent"));Queries=Navigation->GetArrayField(TEXT("queries"));if(Queries.IsEmpty()){Check(false,TEXT("scene queries exist"));Finish();return;}
 HalfHeight=Agent->GetNumberField(TEXT("height_m"))*50;float Radius=Agent->GetNumberField(TEXT("radius_m"))*100;
 FActorSpawnParameters Spawn;Spawn.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;Npc=GetWorld()->SpawnActor<AExamplePawn>(FVector::ZeroVector,FRotator::ZeroRotator,Spawn);
 Npc->GetCapsuleComponent()->SetCapsuleSize(Radius,HalfHeight);Npc->GetCharacterMovement()->SetWalkableFloorAngle(Agent->GetNumberField(TEXT("max_slope_degrees")));Npc->GetCharacterMovement()->MaxStepHeight=Agent->GetNumberField(TEXT("max_step_m"))*100;
 Npc->Body->SetRelativeScale3D(FVector(Radius/50,Radius/50,HalfHeight/50));if(auto* M=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Scene/Tint.Tint"))){auto* D=UMaterialInstanceDynamic::Create(M,this);D->SetVectorParameterValue(TEXT("Tint"),FLinearColor(.1,.75,1));Npc->Body->SetMaterial(0,D);}
 Nav->Configure(300,30,2,25);SceneCamera=GetWorld()->SpawnActor<ACameraActor>();SceneCamera->GetCameraComponent()->SetFieldOfView(60);SetViewTarget(SceneCamera);Select(0);BuildUI();bShowMouseCursor=true;SetInputMode(FInputModeGameAndUI());
}
void AExampleController::Select(int32 Index){Selected=Index;Nav->Clear();auto Q=Queries[Index]->AsObject();Npc->ResetMotor(V(Q->GetArrayField(TEXT("start")))+FVector(0,0,HalfHeight+3));Trace.Empty();MinFoot=MAX_flt;FVector Center=(V(Q->GetArrayField(TEXT("start")))+V(Q->GetArrayField(TEXT("goal"))))/2;SceneCamera->SetActorLocation(Center+FVector(-1800,1200,1800));SceneCamera->SetActorRotation((Center-SceneCamera->GetActorLocation()).Rotation());}
bool AExampleController::StartRoute(){return Nav->Request(FString::Printf(TEXT("scene-%d"),++Serial),Npc,V(Queries[Selected]->AsObject()->GetArrayField(TEXT("goal"))),nullptr,FVector(0,0,-HalfHeight));}
void AExampleController::BuildUI(){auto Column=SNew(SVerticalBox);Column->AddSlot().AutoHeight().Padding(18)[SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Bold",18)).Text_Lambda([this]{return FText::FromString(FString::Printf(TEXT("Generated scene | UE 5.8 | %s | %s %s\nCapsule r=%.2fm h=%.2fm | nav r=%.2fm | slope %.0f deg\nGenerated geometry + native navigation + collision motor"),*Queries[Selected]->AsObject()->GetStringField(TEXT("id")),*Nav->State,Nav->LastError.IsEmpty()?*Nav->Reason:*Nav->LastError,Agent->GetNumberField(TEXT("radius_m")),HalfHeight/50,Agent->GetNumberField(TEXT("navigation_radius_m")),Agent->GetNumberField(TEXT("max_slope_degrees"))));})];auto Row=SNew(SHorizontalBox);for(int I=0;I<Queries.Num()+2;++I){FString Title=I<Queries.Num()?Queries[I]->AsObject()->GetStringField(TEXT("id")):(I==Queries.Num()?TEXT("Run route"):TEXT("Quit"));Row->AddSlot().AutoWidth().Padding(4)[SNew(SButton).ContentPadding(FMargin(10,8)).OnClicked_Lambda([this,I]{if(I==Queries.Num()+1)FPlatformMisc::RequestExit(false);else if(!Testing){if(I==Queries.Num())StartRoute();else Select(I);}return FReply::Handled();})[SNew(STextBlock).Text(FText::FromString(Title))]];}Column->AddSlot().AutoHeight().Padding(12)[Row];UI=Column;GetWorld()->GetGameViewport()->AddViewportWidgetContent(UI.ToSharedRef(),10);}
void AExampleController::Tick(float D){Super::Tick(D);if(Finished||!IsValid(Npc))return;Nav->Step(D);if(Nav->DesiredVelocity.IsNearlyZero()){Npc->ConsumeMovementInputVector();Npc->GetCharacterMovement()->StopMovementImmediately();}else Npc->AddMovementInput(Nav->DesiredVelocity/300,1,true);
 if(Nav->Busy()){FVector Foot=Npc->GetActorLocation()-FVector(0,0,HalfHeight);MinFoot=FMath::Min(MinFoot,(float)Foot.Z/100);SampleClock+=D;if(SampleClock>=.1){SampleClock=0;Trace.Add(MakeShared<FJsonValueArray>(ToSource(Foot)));}}
 if(Testing){if(FPlatformTime::Seconds()-Started>150){Check(false,TEXT("native scene case deadline exceeded"));Finish();return;}TestStep();}}
void AExampleController::EndPlay(const EEndPlayReason::Type R){Nav->Clear();if(UI.IsValid()&&GetWorld()->GetGameViewport())GetWorld()->GetGameViewport()->RemoveViewportWidgetContent(UI.ToSharedRef());Super::EndPlay(R);}
bool AExampleController::Projected(FVector Point)const{auto* N=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());FNavLocation Hit;return N&&N->ProjectPointToNavigation(Point,Hit,FVector(30,30,50))&&FVector::Dist(Point,Hit.Location)<50;}
void AExampleController::Check(bool Ok,const FString& Name){Checks.Add(Name);if(!Ok)Failures.Add(Name);}
void AExampleController::InitialChecks(){TMap<FString,AOAGDGeometry*> Objects;for(TActorIterator<AOAGDGeometry> It(GetWorld());It;++It)if(It->Tags.Num())Objects.Add(It->Tags[0].ToString(),*It);auto Records=Scene->GetArrayField(TEXT("meshes"));Check(Objects.Num()==Records.Num(),TEXT("all generated stable IDs instantiated"));bool Matches=true;for(auto Value:Records){auto R=Value->AsObject();auto* Found=Objects.Find(R->GetStringField(TEXT("id")));if(!Found){Matches=false;continue;}auto* Section=(*Found)->Geometry->GetProcMeshSection(0);auto Positions=R->GetArrayField(TEXT("positions"));if(!Section||!Section->bEnableCollision||Section->ProcVertexBuffer.Num()!=Positions.Num()){Matches=false;continue;}for(int I=0;I<Positions.Num();++I)if(!Section->ProcVertexBuffer[I].Position.Equals(V(Positions[I]->AsArray()),.01))Matches=false;}Check(Matches,TEXT("saved triangle collision vertices match generated specification"));
 auto* N=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());auto* Recast=N?Cast<ARecastNavMesh>(N->GetDefaultNavDataInstance(FNavigationSystem::DontCreate)):nullptr;
 Check(Recast&&Nav->ReadyMap(),TEXT("generated collision baked into native navigation"));Check(FMath::IsNearlyEqual(Npc->GetCapsuleComponent()->GetUnscaledCapsuleRadius(),(float)Agent->GetNumberField(TEXT("radius_m"))*100)&&FMath::IsNearlyEqual(Npc->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight(),HalfHeight),TEXT("actual capsule uses specification dimensions"));
 Check(Recast&&FMath::IsNearlyEqual(Recast->AgentRadius,(float)Agent->GetNumberField(TEXT("navigation_radius_m"))*100)&&FMath::IsNearlyEqual(Recast->AgentHeight,(float)Agent->GetNumberField(TEXT("navigation_height_m"))*100),TEXT("nav bake uses specification clearance"));
 Check(Recast&&FMath::IsNearlyEqual(Recast->AgentMaxSlope,(float)Agent->GetNumberField(TEXT("max_slope_degrees")))&&FMath::IsNearlyEqual(Npc->GetCharacterMovement()->GetWalkableFloorAngle(),(float)Agent->GetNumberField(TEXT("max_slope_degrees"))),TEXT("motor and navigation share slope limit"));
 Check(Recast&&FMath::IsNearlyEqual(Recast->GetAgentMaxStepHeight(ENavigationDataResolution::Default),(float)Agent->GetNumberField(TEXT("max_step_m"))*100),TEXT("navigation uses specification step limit"));
}
void AExampleController::RecordCase(){auto Q=Queries[Selected]->AsObject();FString Prefix=Q->GetStringField(TEXT("id"))+TEXT(": ");bool Expected=Q->GetBoolField(TEXT("expected_reachable"));if(Expected){Check(Nav->State==TEXT("arrived")&&FVector::Dist(Npc->GetActorLocation()-FVector(0,0,HalfHeight),V(Q->GetArrayField(TEXT("goal"))))<65,Prefix+TEXT("collision motor reaches destination"));Check(Trace.Num()>10&&MinFoot>-.15,Prefix+TEXT("sampled trajectory remains supported"));Check(Nav->DesiredVelocity.IsNearlyZero(),Prefix+TEXT("arrival stops steering"));}else Check(Nav->LastError==TEXT("unreachable")&&!Nav->Busy(),Prefix+TEXT("partial path cannot report success"));
 auto R=MakeShared<FJsonObject>();R->SetStringField(TEXT("id"),Q->GetStringField(TEXT("id")));R->SetBoolField(TEXT("expected"),Expected);R->SetBoolField(TEXT("accepted"),Accepted);R->SetStringField(TEXT("state"),Nav->State);R->SetStringField(TEXT("reason"),Nav->Reason);R->SetStringField(TEXT("error"),Nav->LastError);R->SetNumberField(TEXT("seconds"),FPlatformTime::Seconds()-CaseStart);R->SetArrayField(TEXT("path"),Path);R->SetArrayField(TEXT("trajectory"),Trace);R->SetArrayField(TEXT("end"),ToSource(Npc->GetActorLocation()-FVector(0,0,HalfHeight)));Cases.Add(MakeShared<FJsonValueObject>(R));FString Id=Q->GetStringField(TEXT("id"));if(Id==TEXT("curve")||Id==TEXT("ramp")||Id==TEXT("narrow")||Id==TEXT("broken"))FScreenshotRequest::RequestScreenshot(Report+TEXT("-")+Id+TEXT(".png"),true,false);
}
void AExampleController::TestStep(){double Time=FPlatformTime::Seconds()-PhaseTime;if(Phase==0){if(Time<3||(!Projected(V(Queries[0]->AsObject()->GetArrayField(TEXT("start"))))&&Time<30))return;InitialChecks();Select(0);Phase=1;PhaseTime=FPlatformTime::Seconds();}
 else if(Phase==1&&Time>.2){auto Q=Queries[Selected]->AsObject();FString Prefix=Q->GetStringField(TEXT("id"))+TEXT(": ");Check(Projected(V(Q->GetArrayField(TEXT("start")))),Prefix+TEXT("start room has navigation"));Check(Projected(V(Q->GetArrayField(TEXT("goal")))),Prefix+TEXT("goal room has navigation"));CaseStart=FPlatformTime::Seconds();Accepted=StartRoute();Path.Empty();for(auto P:Nav->Path)Path.Add(MakeShared<FJsonValueArray>(ToSource(P)));Check(Accepted==Q->GetBoolField(TEXT("expected_reachable")),Prefix+TEXT("native reachability matches case expectation"));Phase=2;PhaseTime=FPlatformTime::Seconds();}
 else if(Phase==2&&(!Nav->Busy()||Time>26)){RecordCase();Phase=3;PhaseTime=FPlatformTime::Seconds();}
 else if(Phase==3&&Time>.3){if(Selected+1<Queries.Num()){Select(Selected+1);Phase=1;PhaseTime=FPlatformTime::Seconds();}else{Nav->Clear();Check(Nav->Path.IsEmpty()&&Nav->DesiredVelocity.IsNearlyZero(),TEXT("scene cleanup releases navigation"));Finish();}}
}
void AExampleController::Finish(){Finished=true;auto R=MakeShared<FJsonObject>();R->SetStringField(TEXT("engine"),FEngineVersion::Current().ToString());if(Scene.IsValid()){R->SetStringField(TEXT("spec_sha256"),Scene->GetStringField(TEXT("spec_sha256")));R->SetObjectField(TEXT("agent"),Agent);}R->SetStringField(TEXT("input"),TEXT("automated native navigation and collision movement; no human playtest"));R->SetArrayField(TEXT("cases"),Cases);TArray<TSharedPtr<FJsonValue>> C,F;for(auto S:Checks)C.Add(MakeShared<FJsonValueString>(S));for(auto S:Failures)F.Add(MakeShared<FJsonValueString>(S));R->SetArrayField(TEXT("checks"),C);R->SetArrayField(TEXT("failures"),F);FString Text;FJsonSerializer::Serialize(R,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*Report,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);FPlatformMisc::RequestExitWithStatus(false,Failures.Num()?1:0);}
