#include "OAGDConstraints.h"
#include "Components/SkeletalMeshComponent.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimClassInterface.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UnrealType.h"

bool UOAGDConstraintsComponent::Configure(USkeletalMeshComponent* Target,const FString& Json){
 Valid=false;Release();if(Mesh&&FinalizeHandle.IsValid())Mesh->UnregisterOnBoneTransformsFinalizedDelegate(FinalizeHandle);FinalizeHandle.Reset();
 TSharedPtr<FJsonObject> Root;if(!Target||Target->GetOwner()!=GetOwner()||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),Root)||!Root)return false;
 FString Mode;if(!Root->TryGetStringField(TEXT("mode"),Mode)||Mode!=TEXT("contacts_v1"))return false;
 FOAGDConstraintSettings S;
 auto Number=[](const TSharedPtr<FJsonObject>& O,const TCHAR* Key,float& V,float Lo,float Hi,float Scale=1.f){double N;if(!O->TryGetNumberField(Key,N)||!FMath::IsFinite(N)||N<Lo||N>Hi)return false;V=N*Scale;return true;};
 auto Vector=[](const TSharedPtr<FJsonObject>& O,const TCHAR* Key,FVector& V){const TArray<TSharedPtr<FJsonValue>>* A;if(!O->TryGetArrayField(Key,A)||A->Num()!=3)return false;double N[3];for(int I=0;I<3;++I)if(!(*A)[I]->TryGetNumber(N[I])||!FMath::IsFinite(N[I]))return false;V=FVector(N[0],N[1],N[2]);return true;};
 auto Bone=[&](const TSharedPtr<FJsonObject>& O,const TCHAR* Key,FName& N){FString V;if(!O->TryGetStringField(Key,V))return false;N=FName(*V);return Target->GetBoneIndex(N)!=INDEX_NONE;};
 auto Chain=[&](const TSharedPtr<FJsonObject>& O,const TCHAR* Key,TArray<FName>& Names){const TArray<TSharedPtr<FJsonValue>>* A;if(!O->TryGetArrayField(Key,A)||A->Num()!=3)return false;for(const auto& V:*A){FString N;if(!V->TryGetString(N)||Target->GetBoneIndex(FName(*N))==INDEX_NONE)return false;Names.Add(FName(*N));}return Names[0]!=Names[1]&&Names[1]!=Names[2]&&Target->GetParentBone(Names[1])==Names[0]&&Target->GetParentBone(Names[2])==Names[1];};
 const TSharedPtr<FJsonObject>* O;
 if(Root->TryGetObjectField(TEXT("feet"),O)){
  S.Feet=true;if(!Bone(*O,TEXT("pelvis"),S.Pelvis)||!Chain(*O,TEXT("left"),S.Left)||!Chain(*O,TEXT("right"),S.Right))return false;
  if(!Number(*O,TEXT("sole_offset_m"),S.Sole,0,.2,100)||!Number(*O,TEXT("probe_up_m"),S.ProbeUp,.01,1,100)||!Number(*O,TEXT("probe_down_m"),S.ProbeDown,.01,1,100)||!Number(*O,TEXT("max_step_m"),S.MaxStep,.01,.4,100)||!Number(*O,TEXT("max_slope_deg"),S.MaxSlope,1,60)||!Number(*O,TEXT("max_pelvis_m"),S.MaxPelvis,0,.3,100)||!Number(*O,TEXT("blend_s"),S.FeetBlend,.02,1)||!Vector(*O,TEXT("knee_pole"),S.Knee)||S.Knee.IsNearlyZero()||S.MaxStep>FMath::Min(S.ProbeUp,S.ProbeDown))return false;
 }
 if(Root->TryGetObjectField(TEXT("grip"),O)){
  S.Grip=true;if(!Bone(*O,TEXT("main_hand"),S.Main)||!Chain(*O,TEXT("offhand"),S.Offhand)||S.Offhand.Contains(S.Main)||!Number(*O,TEXT("blend_s"),S.GripBlend,.02,1)||!Vector(*O,TEXT("elbow_pole"),S.Elbow)||S.Elbow.IsNearlyZero())return false;
  const TSharedPtr<FJsonObject>* Sockets;const TSharedPtr<FJsonObject>* Native;if(!(*O)->TryGetObjectField(TEXT("sockets"),Sockets)||!(*Sockets)->TryGetObjectField(TEXT("unreal"),Native))return false;
  for(const auto& Pair:TArray<TPair<FString,FTransform*>>{{TEXT("main"),&S.MainSocket},{TEXT("support"),&S.SupportSocket}}){
   const TSharedPtr<FJsonObject>* T;FVector P;const TArray<TSharedPtr<FJsonValue>>* A;
   if(!(*Native)->TryGetObjectField(Pair.Key,T)||!Vector(*T,TEXT("position"),P)||!(*T)->TryGetArrayField(TEXT("rotation_xyzw"),A)||A->Num()!=4)return false;
   double Q[4];for(int I=0;I<4;++I)if(!(*A)[I]->TryGetNumber(Q[I])||!FMath::IsFinite(Q[I]))return false;
   FQuat Rotation(Q[0],Q[1],Q[2],Q[3]);if(!Rotation.IsNormalized())return false;*Pair.Value=FTransform(Rotation,P);
  }
 }
 if(!S.Feet&&!S.Grip)return false;
 Settings=S;Mesh=Target;Valid=true;Reset();FinalizeHandle=Mesh->RegisterOnBoneTransformsFinalizedDelegate(FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateUObject(this,&UOAGDConstraintsComponent::Finalized));return true;
}
void UOAGDConstraintsComponent::Prepare(float D,bool G,FVector2D C,bool H){Delta=FMath::IsFinite(D)?FMath::Clamp(D,0.f,1.f):0;Grounded=G;Contacts=FVector2D(FMath::Clamp(C.X,0.,1.),FMath::Clamp(C.Y,0.,1.));Contact=H;}
bool UOAGDConstraintsComponent::Take(USceneComponent* Target,bool Both){if(!Valid||!Settings.Grip||!IsValid(Target)){Result.GripStatus=TEXT("missing_target");return false;}Release();Prop=Target;Holding=true;TwoHanded=Both;Result.GripStatus=TEXT("attached");return true;}
void UOAGDConstraintsComponent::Release(){Holding=false;Contact=false;Prop=nullptr;Result.GripWeight=0;Result.GripStatus=TEXT("released");++GripGeneration;}
void UOAGDConstraintsComponent::Reset(){Release();++ResetGeneration;Result=FOAGDConstraintResult();Contacts=FVector2D(1,1);}
void UOAGDConstraintsComponent::EndPlay(const EEndPlayReason::Type Reason){if(Mesh&&FinalizeHandle.IsValid())Mesh->UnregisterOnBoneTransformsFinalizedDelegate(FinalizeHandle);Release();Super::EndPlay(Reason);}
FOAGDConstraintInput UOAGDConstraintsComponent::Snapshot()const{
 FOAGDConstraintInput I;I.Valid=Valid&&IsValid(Mesh);if(!I.Valid)return I;I.Settings=Settings;I.Delta=Delta;I.Grounded=Grounded;I.Contacts=Contacts;I.Holding=Holding&&IsValid(Prop);I.TwoHanded=TwoHanded;I.Contact=Contact;I.Mesh=Mesh->GetComponentTransform();I.Actor=GetOwner()->GetActorTransform();
 if(Settings.Feet){FCollisionQueryParams Params(SCENE_QUERY_STAT(OAGDFootIK),false,GetOwner());if(IsValid(Prop))Params.AddIgnoredActor(Prop->GetOwner());
  for(int N=0;N<2;++N){const FVector P=Mesh->GetSocketLocation((N==0?Settings.Left:Settings.Right)[2]);FHitResult Hit;
   I.Hit[N]=GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,Settings.ProbeUp),P-FVector(0,0,Settings.ProbeDown),ECC_Visibility,Params);
   if(I.Hit[N]){I.Point[N]=Hit.ImpactPoint;I.Normal[N]=Hit.ImpactNormal;}
  }
 }return I;
}
void UOAGDConstraintsComponent::Finalized(){
 if(!Valid||!Mesh)return;
 if(auto* Anim=Mesh->GetAnimInstance())if(auto* Interface=IAnimClassInterface::GetFromClass(Anim->GetClass()))for(auto* Field:Interface->GetAnimNodeProperties())if(Field&&Field->Struct==FAnimNode_OAGDConstraints::StaticStruct())Result=Field->ContainerPtrToValuePtr<FAnimNode_OAGDConstraints>(Anim)->Result;
 if(Holding&&!IsValid(Prop)){Release();Result.GripStatus=TEXT("missing_target");}
 if(Holding){FTransform Hand=Mesh->GetSocketTransform(Settings.Main);Hand.SetScale3D(FVector::OneVector);const FTransform Pose=Settings.MainSocket*Hand;Prop->SetWorldLocationAndRotation(Pose.GetLocation(),Pose.GetRotation());Result.Support=Settings.SupportSocket*Pose;}
}
void FAnimNode_OAGDConstraints::Initialize_AnyThread(const FAnimationInitializeContext& C){Source.Initialize(C);}
void FAnimNode_OAGDConstraints::CacheBones_AnyThread(const FAnimationCacheBonesContext& C){Source.CacheBones(C);}
void FAnimNode_OAGDConstraints::Update_AnyThread(const FAnimationUpdateContext& C){Source.Update(C);}
void FAnimNode_OAGDConstraints::PreUpdate(const UAnimInstance* Instance){
 Input.Valid=false;if(auto* Owner=Instance->GetOwningActor())if(auto* C=Owner->FindComponentByClass<UOAGDConstraintsComponent>()){
  Input=C->Snapshot();if(ResetGeneration!=C->ResetGeneration){Result=FOAGDConstraintResult();ResetGeneration=C->ResetGeneration;}
  if(GripGeneration!=C->GripGeneration){Result.GripWeight=0;Result.GripStatus=TEXT("released");GripGeneration=C->GripGeneration;}
 }
}
void FAnimNode_OAGDConstraints::Evaluate_AnyThread(FPoseContext& Output){
 Source.Evaluate(Output);if(!Input.Valid)return;
 const auto& S=Input.Settings;const auto& Container=Output.Pose.GetBoneContainer();const int32 Count=Output.Pose.GetNumBones();
 TArray<FTransform> P;TArray<int32> Parents;P.SetNum(Count);Parents.SetNum(Count);
 for(int I=0;I<Count;++I){FCompactPoseBoneIndex B(I);Parents[I]=Container.GetParentBoneIndex(B).GetInt();P[I]=Output.Pose[B]*(Parents[I]>=0?P[Parents[I]]:Input.Mesh);}
 auto Index=[&](FName Name){return Container.MakeCompactPoseIndex(FMeshPoseBoneIndex(Container.GetPoseBoneIndexForBoneName(Name))).GetInt();};
 auto Set=[&](int I,const FTransform& T){FTransform Old=P[I];for(int J=I+1;J<Count;++J){int A=Parents[J];while(A>=0&&A!=I)A=Parents[A];if(A==I)P[J]=P[J].GetRelativeTransform(Old)*T;}P[I]=T;};
 auto Solve=[&](const TArray<FName>& Names,FVector Target,FVector Pole,float Weight,FQuat Rotation){
  int A=Index(Names[0]),B=Index(Names[1]),C=Index(Names[2]);if(A<0||B<0||C<0)return false;
  FVector Start=P[A].GetLocation(),Middle=P[B].GetLocation(),End=P[C].GetLocation();double L1=FVector::Dist(Start,Middle),L2=FVector::Dist(Middle,End),D=FVector::Dist(Start,Target);
  if(D>L1+L2-.01||D<FMath::Abs(L1-L2)+.01||FMath::Min(L1,L2)<.01)return false;if(Weight<=0)return true;
  FVector Aim=(Target-Start).GetSafeNormal(),Bend=Pole-Aim*FVector::DotProduct(Pole,Aim);
  if(Bend.IsNearlyZero())Bend=Middle-Start-Aim*FVector::DotProduct(Middle-Start,Aim);if(Bend.IsNearlyZero())return false;
  double X=(L1*L1-L2*L2+D*D)/(2*D);FVector Knee=Start+Aim*X+Bend.GetSafeNormal()*FMath::Sqrt(FMath::Max(0.,L1*L1-X*X));
  FTransform T=P[A];T.SetRotation(FQuat::Slerp(FQuat::Identity,FQuat::FindBetweenNormals((Middle-Start).GetSafeNormal(),(Knee-Start).GetSafeNormal()),Weight)*T.GetRotation());Set(A,T);
  T=P[B];T.SetRotation(FQuat::Slerp(FQuat::Identity,FQuat::FindBetweenNormals((P[C].GetLocation()-T.GetLocation()).GetSafeNormal(),(Target-T.GetLocation()).GetSafeNormal()),Weight)*T.GetRotation());Set(B,T);
  T=P[C];T.SetRotation(FQuat::Slerp(T.GetRotation(),Rotation,Weight));Set(C,T);return true;
 };
 auto Approach=[](float Value,float Goal,float Step){return Value+FMath::Clamp(Goal-Value,-Step,Step);};
 if(S.Feet){
  int Pelvis=Index(S.Pelvis);if(Pelvis<0)return;
  FTransform Raw[2];FVector Normals[2]={FVector::UpVector,FVector::UpVector};float Wanted[2]={0,0},Shift=0;
  for(int I=0;I<2;++I){int End=Index((I==0?S.Left:S.Right)[2]);if(End<0)return;Raw[I]=P[End];FVector Point=Raw[I].GetLocation();Result.Goals[I]=Point;Result.FeetStatus[I]=Input.Grounded?TEXT("swing"):TEXT("airborne");
   if(!Input.Grounded||Input.Contacts[I]<=0)continue;if(!Input.Hit[I]){Result.FeetStatus[I]=TEXT("no_ground");continue;}
   FVector N=Input.Normal[I];if(N.Z<FMath::Cos(FMath::DegreesToRadians(S.MaxSlope))){Result.FeetStatus[I]=TEXT("slope_limit");continue;}
   // Project this frame's animated foot onto the locally probed static plane.
   Point.Z=Input.Point[I].Z-(N.X*(Point.X-Input.Point[I].X)+N.Y*(Point.Y-Input.Point[I].Y))/N.Z;Point+=N*S.Sole;
   if(FMath::Abs(Point.Z-Raw[I].GetLocation().Z)>S.MaxStep){Result.FeetStatus[I]=TEXT("step_limit");continue;}
   Result.Goals[I]=Point;Normals[I]=N;Wanted[I]=Input.Contacts[I];Result.FeetStatus[I]=TEXT("contact");Shift=FMath::Min(Shift,float(Point.Z-Raw[I].GetLocation().Z)*Wanted[I]);
  }
  for(int I=0;I<2;++I)Result.Weights[I]=Approach(Result.Weights[I],Wanted[I],Input.Delta/S.FeetBlend);
  Result.Pelvis=Approach(Result.Pelvis,FMath::Clamp(Shift,-S.MaxPelvis,S.MaxPelvis),Input.Delta*S.MaxPelvis/S.FeetBlend);
  FTransform T=P[Pelvis];T.AddToTranslation(FVector(0,0,Result.Pelvis));Set(Pelvis,T);
  for(int I=0;I<2;++I){FVector Goal=Wanted[I]>0?Result.Goals[I]:Raw[I].GetLocation()+FVector(0,0,Result.Pelvis);
   if(!Solve(I==0?S.Left:S.Right,Goal,Input.Actor.TransformVectorNoScale(S.Knee),Result.Weights[I],FQuat::FindBetweenNormals(FVector::UpVector,Normals[I])*Raw[I].GetRotation())){Result.Weights[I]=0;Result.FeetStatus[I]=TEXT("unreachable");}
  }
 }
 if(S.Grip){
  Result.GripStatus=TEXT("released");
  if(Input.Holding){int Main=Index(S.Main);if(Main<0)return;FTransform Hand=P[Main];Hand.SetScale3D(FVector::OneVector);Result.Support=S.SupportSocket*S.MainSocket*Hand;
   Result.GripStatus=!Input.TwoHanded?TEXT("single_hand"):!Input.Contact?TEXT("window_closed"):TEXT("contact");
   Result.GripWeight=Approach(Result.GripWeight,Input.TwoHanded&&Input.Contact?1.f:0.f,Input.Delta/S.GripBlend);
   if(Result.GripWeight>0&&!Solve(S.Offhand,Result.Support.GetLocation(),Input.Actor.TransformVectorNoScale(S.Elbow),Result.GripWeight,Result.Support.GetRotation())){Result.GripWeight=0;Result.GripStatus=TEXT("unreachable");}
  }else Result.GripWeight=0;
 }
 for(int I=0;I<Count;++I)Output.Pose[FCompactPoseBoneIndex(I)]=P[I].GetRelativeTransform(Parents[I]>=0?P[Parents[I]]:Input.Mesh);
}
