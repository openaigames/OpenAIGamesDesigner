#include "OAGDComponents.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Engine/World.h"
#include "ProceduralMeshComponent.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Materials/Material.h"

AOAGDCharacter::AOAGDCharacter() {
    GetCapsuleComponent()->InitCapsuleSize(35.f, 90.f);
    GetCharacterMovement()->MaxWalkSpeed = 500.f;
    GetCharacterMovement()->JumpZVelocity = 500.f;
    GetCharacterMovement()->GravityScale = 1.6f;
    bUseControllerRotationYaw = false;
    CameraArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraArm"));
    CameraArm->SetupAttachment(RootComponent);
    CameraArm->TargetArmLength = 500.f;
    CameraArm->SetRelativeRotation(FRotator(-22,0,0));
    CameraArm->TargetOffset = FVector(0,0,80);
    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraArm);
}
void AOAGDCharacter::MoveWorld(FVector2D Wish) {
    Wish = Wish.GetClampedToMaxSize(1.f);
    AddMovementInput(FVector(Wish.X, Wish.Y, 0));
}
void AOAGDCharacter::Orbit(FVector2D Delta) {
    auto R = CameraArm->GetRelativeRotation();
    R.Yaw += Delta.X; R.Pitch = FMath::Clamp(R.Pitch + Delta.Y, -70.f, 20.f);
    CameraArm->SetRelativeRotation(R);
}
void AOAGDCharacter::ResetMotor(FVector Position) {
    GetCharacterMovement()->StopMovementImmediately();
    ConsumeMovementInputVector();
    SetActorLocation(Position, false, nullptr, ETeleportType::TeleportPhysics);
    GetCharacterMovement()->SetMovementMode(MOVE_Walking);
}
void UOAGDSessionComponent::SetState(FName Value) {
    if (State != Value) { State=Value; StateChanged.Broadcast(State); }
}
void UOAGDSessionComponent::Restart() { ++Generation; SetState(TEXT("playing")); Restarted.Broadcast(Generation); }
bool UOAGDQuery::VisibleHit(UObject* Context, FVector Origin, FVector Direction, float Distance, AActor* Ignore, FHitResult& Hit) {
    if (!Context || !Context->GetWorld() || Distance<=0 || Direction.IsNearlyZero()) return false;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(OAGDVisibleHit), true, Ignore);
    return Context->GetWorld()->LineTraceSingleByChannel(Hit,Origin,Origin+Direction.GetSafeNormal()*Distance,ECC_Visibility,Params);
}
AOAGDGeometry::AOAGDGeometry() {
    Geometry=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("Geometry"));
    RootComponent=Geometry;
    Geometry->SetCollisionProfileName(TEXT("BlockAll"));
    Geometry->bUseComplexAsSimpleCollision=true;
}
bool AOAGDGeometry::LoadScene(UWorld* World, const FString& Path, TArray<AOAGDGeometry*>& Out, FString& Error) {
    FString Text; TSharedPtr<FJsonObject> Doc;
    if (!World || !FFileHelper::LoadFileToString(Text,*Path) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Doc) || !Doc.IsValid()) {
        Error=TEXT("Cannot read scene JSON"); return false;
    }
    FString Coordinates; double SchemaVersion; const TArray<TSharedPtr<FJsonValue>>* Records;
    if (!Doc->TryGetNumberField(TEXT("schema_version"),SchemaVersion) || SchemaVersion!=1 || !Doc->TryGetStringField(TEXT("coordinates"),Coordinates) || Coordinates!=TEXT("RH_Y_UP_METRES_CCW") || !Doc->TryGetArrayField(TEXT("meshes"),Records)) {
        Error=TEXT("Unsupported schema/coordinates/meshes"); return false;
    }
    struct FMesh { FString Id; TArray<FVector> V,N; TArray<int32> I; TArray<FLinearColor> C; bool Collision; };
    TArray<FMesh> Validated; TSet<FString> Ids;
    auto ReadVector=[](const TSharedPtr<FJsonValue>& Value,FVector& Result)->bool {
        const TArray<TSharedPtr<FJsonValue>>* A;
        if(!Value->TryGetArray(A)||A->Num()!=3) return false;
        double X,Y,Z;
        if(!(*A)[0]->TryGetNumber(X)||!(*A)[1]->TryGetNumber(Y)||!(*A)[2]->TryGetNumber(Z)||!FMath::IsFinite(X)||!FMath::IsFinite(Y)||!FMath::IsFinite(Z)) return false;
        Result=FVector(-Z,X,Y); return true; // RH Y-up -> UE forward X, right Y, up Z.
    };
    for (const auto& Value:*Records) {
        auto R=Value->AsObject(); FMesh M;
        const TArray<TSharedPtr<FJsonValue>> *V,*N,*I,*C;
        if(!R.IsValid()||!R->TryGetStringField(TEXT("id"),M.Id)||M.Id.IsEmpty()||Ids.Contains(M.Id)||!R->TryGetBoolField(TEXT("collision"),M.Collision)||
           !R->TryGetArrayField(TEXT("positions"),V)||!R->TryGetArrayField(TEXT("normals"),N)||!R->TryGetArrayField(TEXT("indices"),I)||!R->TryGetArrayField(TEXT("color"),C)||
           V->Num()!=N->Num()||V->Num()==0||I->Num()==0||I->Num()%3||C->Num()!=4) {Error=TEXT("Invalid mesh record");return false;}
        Ids.Add(M.Id);
        double RGBA[4];
        for(int32 K=0;K<4;++K)if(!(*C)[K]->TryGetNumber(RGBA[K])||!FMath::IsFinite(RGBA[K])||RGBA[K]<0||RGBA[K]>1){Error=TEXT("Invalid color");return false;}
        const FLinearColor Tint(RGBA[0],RGBA[1],RGBA[2],RGBA[3]);
        for(int32 K=0;K<V->Num();++K) {FVector P,Normal; if(!ReadVector((*V)[K],P)||!ReadVector((*N)[K],Normal)){Error=TEXT("Invalid vertex");return false;} M.V.Add(P*100); M.N.Add(Normal); M.C.Add(Tint);}
        for(const auto& Idx:*I) {double D;if(!Idx->TryGetNumber(D)||D<0||D>=M.V.Num()||D!=FMath::FloorToDouble(D)){Error=TEXT("Invalid index");return false;}M.I.Add((int32)D);}
        // Reflection above reverses handedness. UE uses clockwise front faces;
        // these two conventions cancel: keep source triangle index order.
        Validated.Add(MoveTemp(M));
    }
    for(const auto& M:Validated) {
        auto* Actor=World->SpawnActor<AOAGDGeometry>();
        if(!Actor){Error=TEXT("Cannot spawn geometry");for(auto* A:Out) A->Destroy();Out.Empty();return false;}
        Actor->Tags.Add(FName(*M.Id));
        Actor->Geometry->CreateMeshSection_LinearColor(0,M.V,M.I,M.N,TArray<FVector2D>(),M.C,TArray<FProcMeshTangent>(),M.Collision);
        Actor->Geometry->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial")));
        Out.Add(Actor);
    }
    return true;
}
