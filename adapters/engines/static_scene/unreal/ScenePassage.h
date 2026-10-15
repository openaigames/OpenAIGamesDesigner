#pragma once
#include "CoreMinimal.h"
#include "Engine/World.h"
#include "CollisionQueryParams.h"

namespace OAGDScene {
struct FPassageResult {
 bool Valid=false;
 bool Clear=false;
 bool InitialOverlap=false;
 float SafeFraction=0;
};
// Call in a running native world after collision has been registered.
// Inputs use the shared RH Y-up metre space; native world = (-Z, X, Y) * 100.
inline FPassageResult Passage(UWorld* World,FVector Start,FVector Finish,double Radius,double Height,ECollisionChannel Channel=ECC_Visibility) {
 FPassageResult R;
 if(!World||Start.ContainsNaN()||Finish.ContainsNaN()||!FMath::IsFinite(Radius)||!FMath::IsFinite(Height)||Radius<=0||Height<2*Radius)return R;
 auto Convert=[](FVector P){return FVector(-P.Z,P.X,P.Y)*100;};
 auto Shape=FCollisionShape::MakeCapsule(float(Radius*100),float(Height*50));
 FCollisionQueryParams Query;FHitResult Hit;
 R.Valid=true;
 R.InitialOverlap=World->OverlapBlockingTestByChannel(Convert(Start),FQuat::Identity,Channel,Shape,Query);
 bool Blocked=World->SweepSingleByChannel(Hit,Convert(Start),Convert(Finish),FQuat::Identity,Channel,Shape,Query);
 R.Clear=!R.InitialOverlap&&!Blocked;R.SafeFraction=R.InitialOverlap?0:(Blocked?Hit.Time:1);
 return R;
}
}
