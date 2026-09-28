#include "ObservationFixture.h"
#include "Modules/ModuleManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InputComponent.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "Engine/World.h"
#include "UObject/ConstructorHelpers.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "InputCoreTypes.h"
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, ToolkitObservation, "ToolkitObservation");

static FString Encode(const TSharedRef<FJsonObject>& Object) {
    FString Text; FJsonSerializer::Serialize(Object,TJsonWriterFactory<>::Create(&Text)); return Text;
}
UObservationSettings::UObservationSettings() {
    DamageCurve = CreateDefaultSubobject<UCurveFloat>(TEXT("DamageProfile"));
    DamageCurve->FloatCurve.AddKey(0,10); DamageCurve->FloatCurve.AddKey(1,20);
}
FString UObservationSettings::ExportAuthorData() const {
    auto O=MakeShared<FJsonObject>();
    O->SetNumberField(TEXT("walk_speed"),WalkSpeed); O->SetNumberField(TEXT("windup"),Windup);
    O->SetNumberField(TEXT("cleanup_delay"),CleanupDelay);
    TArray<TSharedPtr<FJsonValue>> Keys;
    if(DamageCurve) for(auto It=DamageCurve->FloatCurve.GetKeyIterator();It;++It) {
        TArray<TSharedPtr<FJsonValue>> Pair{MakeShared<FJsonValueNumber>(It->Time),MakeShared<FJsonValueNumber>(It->Value)};
        Keys.Add(MakeShared<FJsonValueArray>(Pair));
    }
    O->SetArrayField(TEXT("damage_keys"),Keys); return Encode(O);
}
bool UObservationSettings::ApplyAuthorData(const FString& Patch) {
    TSharedPtr<FJsonObject> O;
    if(Patch.Len()>65536 || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Patch),O)||!O.IsValid())return false;
    const TSet<FString> Allowed{TEXT("walk_speed"),TEXT("windup"),TEXT("cleanup_delay"),TEXT("damage_keys")};
    for(const auto& P:O->Values)if(!Allowed.Contains(FString(P.Key.ToView())))return false;
    double Speed=WalkSpeed,Start=Windup,Delay=CleanupDelay;
    for(auto Pair:{TPair<FString,double*>(TEXT("walk_speed"),&Speed),TPair<FString,double*>(TEXT("windup"),&Start),TPair<FString,double*>(TEXT("cleanup_delay"),&Delay)}) {
        if(O->HasField(Pair.Key)&&!O->TryGetNumberField(Pair.Key,*Pair.Value))return false;
        if(!FMath::IsFinite(*Pair.Value))return false;
    }
    if(Speed<=0||Speed>1500||Start<.01||Start>5||Delay<0||Delay>2)return false;
    TArray<FVector2D> NewKeys;
    if(O->HasField(TEXT("damage_keys"))) {
        const TArray<TSharedPtr<FJsonValue>>* Keys;
        if(!O->TryGetArrayField(TEXT("damage_keys"),Keys)||Keys->Num()<2||Keys->Num()>128)return false;
        double Previous=-1;
        for(const auto& K:*Keys) {
            const TArray<TSharedPtr<FJsonValue>>* Pair; double Time,Value;
            if(!K->TryGetArray(Pair)||Pair->Num()!=2||!(*Pair)[0]->TryGetNumber(Time)||!(*Pair)[1]->TryGetNumber(Value))return false;
            if(!FMath::IsFinite(Time)||!FMath::IsFinite(Value)||Time<=Previous||Value<0)return false;
            Previous=Time;NewKeys.Add(FVector2D(Time,Value));
        }
    }
    Modify();WalkSpeed=Speed;Windup=Start;CleanupDelay=Delay;
    if(NewKeys.Num()) {
        DamageCurve->Modify(); DamageCurve->FloatCurve.Reset();
        for(const auto& K:NewKeys) { auto H=DamageCurve->FloatCurve.AddKey(K.X,K.Y);DamageCurve->FloatCurve.SetKeyInterpMode(H,RCIM_Linear); }
    }
    MarkPackageDirty();return true;
}

AObservationPawn::AObservationPawn() {
    PrimaryActorTick.bCanEverTick=true;
    Capsule=CreateDefaultSubobject<UCapsuleComponent>(TEXT("Capsule"));RootComponent=Capsule;
    Capsule->InitCapsuleSize(24,50);Capsule->SetCollisionProfileName(TEXT("Pawn"));
    Body=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));Body->SetupAttachment(Capsule);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Mesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    Body->SetStaticMesh(Mesh.Object);Body->SetRelativeScale3D(FVector(.48,.48,1));Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GripAnchor=CreateDefaultSubobject<USceneComponent>(TEXT("GripAnchor"));GripAnchor->SetupAttachment(Capsule);
    GripAnchor->SetRelativeLocation(FVector(35,20,0));
    Movement=CreateDefaultSubobject<UFloatingPawnMovement>(TEXT("Movement"));Movement->UpdatedComponent=Capsule;
    AutoPossessPlayer=EAutoReceiveInput::Player0;
}
void AObservationPawn::BeginPlay() {
    Super::BeginPlay();
    StartingTransform=GetActorTransform();
    if(auto PC=Cast<APlayerController>(GetController()))PC->ClientSetHUD(AObservationHUD::StaticClass());
    if(!Settings)Settings=NewObject<UObservationSettings>(this);
    AppliedWalkSpeed=Settings->WalkSpeed;Movement->MaxSpeed=AppliedWalkSpeed;Movement->Acceleration=3000;Movement->Deceleration=4000;
    RuntimeWeapon=NewObject<UStaticMeshComponent>(this,TEXT("RuntimeWeapon"));
    RuntimeWeapon->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
    RuntimeWeapon->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    RuntimeWeapon->CreationMethod=EComponentCreationMethod::Instance;
    AddInstanceComponent(RuntimeWeapon);RuntimeWeapon->RegisterComponent();
    RuntimeWeapon->AttachToComponent(GripAnchor,FAttachmentTransformRules::KeepRelativeTransform);
    RuntimeWeapon->SetRelativeScale3D(FVector(.7,.08,.08));
    Mark(TEXT("runtime_binding_created"),TEXT("RuntimeWeapon -> GripAnchor; source constructor anchor, BeginPlay attachment"));
}
void AObservationPawn::Mark(const FString& Event,const FString& Detail) {
    auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("id"),FString::FromInt(Events.Num()));
    O->SetNumberField(TEXT("time"),GetWorld()->GetTimeSeconds());O->SetStringField(TEXT("event"),Event);
    auto D=MakeShared<FJsonObject>();D->SetStringField(TEXT("detail"),Detail);D->SetStringField(TEXT("state"),ActionState);D->SetBoolField(TEXT("effect_active"),EffectActive);
    D->SetNumberField(TEXT("damage"),AppliedDamage);D->SetNumberField(TEXT("target_health"),TargetHealth);O->SetObjectField(TEXT("data"),D);
    if(Events.Num()<10000)Events.Add(MakeShared<FJsonValueObject>(O));
}
FString AObservationPawn::ExportObservationEvents() const { FString Out;FJsonSerializer::Serialize(Events,TJsonWriterFactory<>::Create(&Out));return Out; }
void AObservationPawn::Attack() {
    Mark(TEXT("input_request"),TEXT("attack gameplay handler; see session input_mode"));
    if(ActionState!=TEXT("idle")||TargetHealth<=0){Mark(TEXT("input_rejected"));return;}
    if(CleanupRemaining>=0)FinishCleanup();
    ActionState=TEXT("windup");PhaseTime=0;Mark(TEXT("action_started"));
}
void AObservationPawn::Cancel() {
    Mark(TEXT("input_request"),TEXT("cancel"));if(ActionState==TEXT("idle"))return;
    ActionState=TEXT("idle");Mark(TEXT("cancel"));CleanupRemaining=Settings->CleanupDelay;
    if(CleanupRemaining==0)FinishCleanup();
}
void AObservationPawn::FinishCleanup(){EffectActive=false;CleanupRemaining=-1;if(RuntimeWeapon)RuntimeWeapon->SetRelativeRotation(FRotator::ZeroRotator);Mark(TEXT("cleanup"));}
void AObservationPawn::SetTravel(float X,float Y){Travel=FVector(X,Y,0).GetClampedToMaxSize(1);Mark(TEXT("travel_request"));}
void AObservationPawn::RestartEncounter(){
    FinishCleanup();TargetHealth=42;ActionState=TEXT("idle");PhaseTime=0;AppliedDamage=0;Travel=FVector::ZeroVector;
    Movement->StopMovementImmediately();SetActorTransform(StartingTransform);Mark(TEXT("restart"));
}
void AObservationPawn::Tick(float Delta) {
    Super::Tick(Delta);AddMovementInput(Travel,1);
    if(CleanupRemaining>=0){CleanupRemaining-=Delta;if(CleanupRemaining<=0)FinishCleanup();}
    if(ActionState==TEXT("idle"))return;
    PhaseTime+=Delta;
    if(ActionState==TEXT("windup")&&PhaseTime>=Settings->Windup) {
        ActionState=TEXT("active");EffectActive=true;Mark(TEXT("rule_commit"));Mark(TEXT("vfx_start"));
        FHitResult Hit; FCollisionQueryParams Q(SCENE_QUERY_STAT(ObservationAttack),false,this);
        FVector Start=GetActorLocation();bool Blocking=GetWorld()->LineTraceSingleByChannel(Hit,Start,Start+GetActorForwardVector()*250,ECC_Visibility,Q);
        AppliedDamage=Blocking?Settings->DamageCurve->GetFloatValue(.5):0;
        if(Blocking)TargetHealth=FMath::Max(0.f,TargetHealth-AppliedDamage);
        Mark(Blocking?TEXT("hit"):TEXT("miss"),Blocking?Hit.GetActor()->GetName():TEXT(""));
        if(Blocking&&TargetHealth<=0)Mark(TEXT("victory"));
    }
    if(RuntimeWeapon&&EffectActive)RuntimeWeapon->SetRelativeRotation(FRotator(0,FMath::Sin(PhaseTime*15)*65,0));
    if(PhaseTime>=Settings->Windup+.28f&&ActionState==TEXT("active")){ActionState=TEXT("recovery");Mark(TEXT("recovery"));FinishCleanup();}
    if(PhaseTime>=Settings->Windup+.48f){ActionState=TEXT("idle");Mark(TEXT("ready"));}
}
void AObservationPawn::SetupPlayerInputComponent(UInputComponent* Input) {
    Super::SetupPlayerInputComponent(Input);
    Input->BindKey(EKeys::LeftMouseButton,IE_Pressed,this,&AObservationPawn::Attack);
    Input->BindKey(EKeys::SpaceBar,IE_Pressed,this,&AObservationPawn::Cancel);
    Input->BindKey(EKeys::R,IE_Pressed,this,&AObservationPawn::RestartEncounter);
    Input->BindKey(EKeys::W,IE_Pressed,this,&AObservationPawn::Forward);
    Input->BindKey(EKeys::W,IE_Released,this,&AObservationPawn::Stop);
    Input->BindKey(EKeys::S,IE_Pressed,this,&AObservationPawn::Back);
    Input->BindKey(EKeys::S,IE_Released,this,&AObservationPawn::Stop);
}

void AObservationHUD::DrawHUD(){
    Super::DrawHUD();auto P=Cast<AObservationPawn>(GetOwningPawn());if(!P)return;
    DrawRect(FLinearColor(0.f,0.f,0.f,.75f),12,12,670,112);
    DrawText(TEXT("TOOLKIT NATIVE PROBE | W/S move | Click attack | Space cancel | R retry"),FLinearColor::White,24,24,nullptr,1.f);
    DrawText(FString::Printf(TEXT("Target HP %.0f | Damage %.0f | %s"),P->TargetHealth,P->AppliedDamage,*P->ActionState),FLinearColor::White,24,52,nullptr,1.3f);
    if(P->TargetHealth<=0)DrawText(TEXT("TARGET CLEARED - Press R to retry"),FLinearColor::Green,24,82,nullptr,1.3f);
}
