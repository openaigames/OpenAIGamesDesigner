#include "ExampleGame.h"
#include "Modules/ModuleManager.h"
#include "Components/InputComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/Engine.h"
#include "UnrealClient.h"
#include "Misc/EngineVersion.h"
#include "Materials/MaterialInstanceDynamic.h"

IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, OAGDExamples, "OAGDExamples");
AExamplePlayer::AExamplePlayer() {
    auto* Body=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("GreyboxBody"));
    Body->SetupAttachment(RootComponent);
    Body->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
    Body->SetRelativeScale3D(FVector(.7,.7,1.8));
    Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Body->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ExampleTint.ExampleTint")));
}
void AExamplePlayer::SetupPlayerInputComponent(UInputComponent* Input) {
    Super::SetupPlayerInputComponent(Input);
    Input->BindAxis(TEXT("Forward"),this,&AExamplePlayer::Forward);
    Input->BindAxis(TEXT("Right"),this,&AExamplePlayer::Right);
    Input->BindAxis(TEXT("LookX"),this,&AExamplePlayer::LookX);
    Input->BindAxis(TEXT("LookY"),this,&AExamplePlayer::LookY);
    Input->BindKey(EKeys::E,IE_Pressed,this,&AExamplePlayer::Act);
    Input->BindKey(EKeys::R,IE_Pressed,this,&AExamplePlayer::Retry);
    Input->BindKey(EKeys::SpaceBar,IE_Pressed,this,&AExamplePlayer::TryJump);
    Input->BindKey(EKeys::SpaceBar,IE_Released,this,&ACharacter::StopJumping);
}
void AExamplePlayer::Forward(float Value) {
    auto* G=GetWorld()->GetAuthGameMode<AExampleGame>();
    if(!G||G->Session->State!=TEXT("playing"))return;
    FVector Dir=FRotationMatrix(FRotator(0,CameraArm->GetRelativeRotation().Yaw,0)).GetUnitAxis(EAxis::X);
    MoveWorld(FVector2D(Dir.X,Dir.Y)*Value);
}
void AExamplePlayer::Right(float Value) {
    auto* G=GetWorld()->GetAuthGameMode<AExampleGame>();
    if(!G||G->Session->State!=TEXT("playing"))return;
    FVector Dir=FRotationMatrix(FRotator(0,CameraArm->GetRelativeRotation().Yaw,0)).GetUnitAxis(EAxis::Y);
    MoveWorld(FVector2D(Dir.X,Dir.Y)*Value);
}
void AExamplePlayer::Tick(float Delta) {
    Super::Tick(Delta);
    // CharacterMovement consumes the combined world-space input once per frame.
    // Individual axis delegates overwrite a diagonal direction (including on release).
    const FVector Wish=GetLastMovementInputVector();
    if(!Wish.IsNearlyZero())Facing=Wish.GetSafeNormal();
}
void AExamplePlayer::LookX(float Value) { if(auto* PC=Cast<APlayerController>(Controller);PC&&PC->IsInputKeyDown(EKeys::RightMouseButton))Orbit(FVector2D(Value,0)); }
void AExamplePlayer::LookY(float Value) { if(auto* PC=Cast<APlayerController>(Controller);PC&&PC->IsInputKeyDown(EKeys::RightMouseButton))Orbit(FVector2D(0,Value)); }
void AExamplePlayer::Act(){if(auto* G=GetWorld()->GetAuthGameMode<AExampleGame>())G->Act();}
void AExamplePlayer::Retry(){if(auto* G=GetWorld()->GetAuthGameMode<AExampleGame>())G->Session->Restart();}
void AExamplePlayer::TryJump(){if(auto* G=GetWorld()->GetAuthGameMode<AExampleGame>();G&&G->Session->State==TEXT("playing"))Jump();}
AExampleGame::AExampleGame() {
    PrimaryActorTick.bCanEverTick=true;
    DefaultPawnClass=AExamplePlayer::StaticClass(); HUDClass=AExampleHUD::StaticClass();
    Session=CreateDefaultSubobject<UOAGDSessionComponent>(TEXT("Session"));
}
static AActor* Box(UWorld* World,FVector P,FVector Scale,FLinearColor Color) {
    auto* A=World->SpawnActor<AStaticMeshActor>(P,FRotator::ZeroRotator);
    auto* M=A->GetStaticMeshComponent(); M->SetMobility(EComponentMobility::Movable);
    M->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
    M->SetWorldScale3D(Scale);M->SetCollisionProfileName(TEXT("BlockAll"));
    if(auto* Tint=M->CreateDynamicMaterialInstance(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ExampleTint.ExampleTint"))))Tint->SetVectorParameterValue(TEXT("Tint"),Color);
    return A;
}
void AExampleGame::BeginPlay() {
    Super::BeginPlay();
    Testing=FParse::Param(FCommandLine::Get(),TEXT("OAGDSelfTest"));
    FString Config;TSharedPtr<FJsonObject> Doc;
    if(FFileHelper::LoadFileToString(Config,*(FPaths::ProjectContentDir()/TEXT("OAGDData/scenario.json")))&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Config),Doc))Scenario=Doc->GetStringField(TEXT("scenario"));
    FString Error;
    bool Loaded=AOAGDGeometry::LoadScene(GetWorld(),FPaths::ProjectContentDir()/TEXT("generated/parts/scene.json"),Generated,Error);
    Check(Loaded&&Generated.Num()==8,TEXT("generated parts imported with stable IDs: ")+Error);
    auto* Light=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,600),FRotator(-55,-25,0));
    Light->GetLightComponent()->SetIntensity(3.f);
    auto* Sky=GetWorld()->SpawnActor<ASkyLight>(); Sky->GetLightComponent()->SetIntensity(1.f);
    Target=Box(GetWorld(),FVector(200,0,70),FVector(1,1,1.4),FLinearColor(.95f,.6f,.12f));
    Door=Box(GetWorld(),FVector(400,0,100),FVector(.3,2,2),FLinearColor(.15f,.65f,.75f));
    Session->Restarted.AddDynamic(this,&AExampleGame::ResetRules);
}
void AExampleGame::ResetRules(int32 Generation) {
    TargetHP=PlayerHP=3;HasKey=DoorOpen=false;LastHit=-100;
    Target->SetActorHiddenInGame(false);Target->SetActorEnableCollision(true);
    Door->SetActorHiddenInGame(Scenario!=TEXT("puzzle"));Door->SetActorEnableCollision(Scenario==TEXT("puzzle"));
    if(Player){Player->ResetMotor(FVector(-200,0,92));Player->Facing=FVector::ForwardVector;}
}
void AExampleGame::Tick(float Delta) {
    Super::Tick(Delta);Time+=Delta;
    if(!Player) {Player=Cast<AExamplePlayer>(UGameplayStatics::GetPlayerPawn(this,0));if(Player)ResetRules(0);return;}
    if(Player->GetActorLocation().Z<-500)Damage(3);
    if(Scenario==TEXT("puzzle")&&DoorOpen&&Player->GetActorLocation().X>500)Session->SetState(TEXT("won"));
    if(Testing)TestStep(Delta);
}
void AExampleGame::Act() {
    if(!Player||Session->State!=TEXT("playing")||Time-LastHit<.2)return;
    FHitResult Hit;
    if(!UOAGDQuery::VisibleHit(this,Player->GetActorLocation(),Player->Facing,260,Player,Hit))return;
    if(Hit.GetActor()==Target) {
        LastHit=Time;
        if(Scenario==TEXT("training")) {if(--TargetHP==0)Session->SetState(TEXT("won"));}
        else {HasKey=true;Target->SetActorHiddenInGame(true);Target->SetActorEnableCollision(false);}
    } else if(Hit.GetActor()==Door&&HasKey) {DoorOpen=true;Door->SetActorHiddenInGame(true);Door->SetActorEnableCollision(false);}
}
void AExampleGame::Damage(int32 Amount){PlayerHP=FMath::Max(0,PlayerHP-Amount);if(PlayerHP==0)Session->SetState(TEXT("lost"));}
void AExampleGame::Check(bool Condition,const FString& Name){++Assertions;Checks.Add(Name);if(!Condition){Failures.Add(Name);UE_LOG(LogTemp,Error,TEXT("OAGD check failed: %s"),*Name);}}
void AExampleGame::Next(){++Stage;StageTime=0;}
void AExampleGame::TestStep(float Delta) {
    StageTime+=Delta;
    switch(Stage) {
    case 0: if(StageTime>.5){Check(Player->GetCharacterMovement()->IsMovingOnGround(),TEXT("generated floor collision"));Before=Player->GetActorLocation();Next();} break;
    case 1: Player->Right(1);if(StageTime>.5){Check(Player->GetActorLocation().Y>Before.Y+100,TEXT("game input handler moves native motor"));Player->ResetMotor(FVector(480,0,92));Next();}break;
    case 2: Player->Forward(1);if(StageTime>.8){Check(Player->GetActorLocation().X>530&&Player->GetActorLocation().X<565,TEXT("generated wall blocks motor"));FHitResult Hit;Check(UOAGDQuery::VisibleHit(this,FVector(480,0,100),FVector::ForwardVector,400,Player,Hit)&&Hit.Location.X<610,TEXT("query stops at obstruction"));Session->Restart();Next();}break;
    case 3: if(StageTime>.1){Act();Check(TargetHP==3&&!HasKey,TEXT("interaction rejects out of range"));Player->ResetMotor(FVector(0,0,92));Next();}break;
    case 4: if(StageTime>.3){Act();if(Scenario==TEXT("puzzle")){Check(HasKey,TEXT("puzzle collects visible key"));Player->ResetMotor(FVector(200,0,92));}Next();}break;
    case 5: if(StageTime>.3){Act();if(Scenario==TEXT("puzzle"))Check(DoorOpen&&!Door->GetActorEnableCollision(),TEXT("key opens door and releases collision"));Next();}break;
    case 6: if(Scenario==TEXT("puzzle"))Player->Forward(1);if(StageTime>1){if(Scenario==TEXT("training"))Act();Check(Session->State==TEXT("won"),TEXT("complete scenario"));Session->Restart();Next();}break;
    case 7: if(StageTime>.2){Check(TargetHP==3&&!HasKey&&!DoorOpen&&Session->State==TEXT("playing"),TEXT("restart restores game-owned state"));Damage(3);Check(Session->State==TEXT("lost"),TEXT("failure state"));Session->Restart();Next();}break;
    case 8: if(StageTime>.2){Check(PlayerHP==3&&Session->State==TEXT("playing")&&Player->GetVelocity().Size()<2,TEXT("retry clears movement and failure"));TArray<AOAGDGeometry*> Terrain;FString Error;Check(AOAGDGeometry::LoadScene(GetWorld(),FPaths::ProjectContentDir()/TEXT("generated/terrain/scene.json"),Terrain,Error)&&Terrain.Num()==13,TEXT("terrain and clearance scatter imported"));for(auto* A:Terrain)A->SetActorLocation(FVector(0,3500,0));Next();}break;
    case 9: if(StageTime>.3){FHitResult Hit;Check(UOAGDQuery::VisibleHit(this,FVector(0,3500,500),FVector::DownVector,1000,Player,Hit)&&FMath::Abs(Hit.Location.Z)<1,TEXT("terrain road height and centimetre conversion"));if(GEngine&&GEngine->GameViewport)FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir()/TEXT("validation.png"),false,false);Next();}break;
    case 10: if(StageTime>.5){Finish();Testing=false;}break;
    }
}
void AExampleGame::Finish() {
    auto Report=MakeShared<FJsonObject>();Report->SetStringField(TEXT("scenario"),Scenario);Report->SetStringField(TEXT("engine"),FEngineVersion::Current().ToString());Report->SetNumberField(TEXT("assertions"),Assertions);
    TArray<TSharedPtr<FJsonValue>> Names,Errors;for(const auto& N:Checks)Names.Add(MakeShared<FJsonValueString>(N));for(const auto& E:Failures)Errors.Add(MakeShared<FJsonValueString>(E));Report->SetArrayField(TEXT("checks"),Names);Report->SetArrayField(TEXT("failures"),Errors);Report->SetStringField(TEXT("input"),TEXT("game input handlers + native physics; not manual play"));
    FString Json;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Json));FFileHelper::SaveStringToFile(Json,*(FPaths::ProjectSavedDir()/TEXT("validation.json")));
    UE_LOG(LogTemp,Display,TEXT("OAGD_TEST_%s count=%d"),Failures.IsEmpty()?TEXT("PASS"):TEXT("FAIL"),Assertions);
    UKismetSystemLibrary::QuitGame(this,UGameplayStatics::GetPlayerController(this,0),EQuitPreference::Quit,false);
}
void AExampleHUD::DrawHUD() {
    Super::DrawHUD();auto* G=GetWorld()->GetAuthGameMode<AExampleGame>();if(!G)return;
    DrawText(FString::Printf(TEXT("OAGD | %s | %s\nWASD move   Space jump   E act   R restart   RMB orbit\nHP %d   Target %d   Key %s   Door %s"),*G->Scenario,*G->Session->State.ToString(),G->PlayerHP,G->TargetHP,G->HasKey?TEXT("yes"):TEXT("no"),G->DoorOpen?TEXT("open"):TEXT("closed")),FColor::White,24,24,nullptr,1.4f);
}
