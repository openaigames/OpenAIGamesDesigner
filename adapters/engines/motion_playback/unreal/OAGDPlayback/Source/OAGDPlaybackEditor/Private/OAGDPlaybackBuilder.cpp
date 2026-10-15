#include "OAGDPlaybackBuilder.h"
#include "OAGDPlayback.h"
#include "AnimGraphNode_OAGDConstraints.h"
#include "Modules/ModuleManager.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/AnimSequence.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_SequencePlayer.h"
#include "AnimGraphNode_BlendListByInt.h"
#include "AnimGraphNode_TwoWayBlend.h"
#include "AnimGraphNode_LayeredBoneBlend.h"
#include "Animation/Skeleton.h"
#include "K2Node_VariableGet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphSchema.h"
#include "UObject/UnrealType.h"
IMPLEMENT_MODULE(FDefaultModuleImpl,OAGDPlaybackEditor)

bool UOAGDPlaybackBuilder::BuildGraph(UAnimBlueprint* BP,UOAGDPlaybackSet* Set,float BlendSeconds) {
 if(!BP||!Set||Set->Clips.IsEmpty()||!BP->ParentClass->IsChildOf(UOAGDPlaybackAnimInstance::StaticClass())||BlendSeconds<0||BlendSeconds>2)return false;
 if(Set->RootMotionEnabled&&(BlendSeconds!=0||Set->LocomotionEnabled||Set->LayersEnabled))return false;
 UEdGraph* Graph=nullptr;UAnimGraphNode_Root* Root=nullptr;
 for(const auto& G:BP->FunctionGraphs)for(const auto& N:G->Nodes)if(auto* R=Cast<UAnimGraphNode_Root>(N.Get())){Graph=G.Get();Root=R;}
 if(!Graph||!Root||Graph->Nodes.Num()!=1)return false;
 for(const auto& B:Set->Clips)if(!B.Sequence||B.Sequence->GetSkeleton()!=BP->TargetSkeleton)return false;
 const auto* Schema=Graph->GetSchema();
 auto* Blend=NewObject<UAnimGraphNode_BlendListByInt>(Graph);Graph->AddNode(Blend,true,false);Blend->CreateNewGuid();Blend->PostPlacedNewNode();
 // PostPlacedNewNode registers UE's exposed-input binding/compiler extensions
 // and adds a second pose. Skipping it leaves a graph that compiles but stays idle.
 for(int32 I=2;I<Set->Clips.Num();++I)Blend->Node.AddPose();
 // UE 5.8 folded node config is reflected rather than public C++ fields.
 if(auto* Field=FindFProperty<FEnumProperty>(FAnimNode_BlendListBase::StaticStruct(),TEXT("ChildUpateMode")))
  Field->GetUnderlyingProperty()->SetIntPropertyValue(Field->ContainerPtrToValuePtr<void>(&Blend->Node),static_cast<uint64>(EBlendListChildUpdateMode::ResetChildOnActivate));
 Blend->AllocateDefaultPins();Blend->NodePosX=-240;
 auto Connect=[&](UEdGraphPin* A,UEdGraphPin* B){return A&&B&&Schema->TryCreateConnection(A,B);};
 if(!Set->LayersEnabled&&!Connect(Blend->FindPin(TEXT("Pose")),Root->FindPin(TEXT("Result"))))return false;
 auto Variable=[&](FName Name,int32 Y){auto* V=NewObject<UK2Node_VariableGet>(Graph);Graph->AddNode(V,true,false);V->CreateNewGuid();V->VariableReference.SetSelfMember(Name);V->AllocateDefaultPins();V->NodePosX=-800;V->NodePosY=Y;return V;};
 auto* Index=Variable(TEXT("StateIndex"),-250);auto* Rate=Variable(TEXT("PlaybackRate"),-400);
 if(!Connect(Index->FindPin(TEXT("StateIndex")),Blend->FindPin(TEXT("ActiveChildIndex"))))return false;
 int32 LocomotionRow=0;
 auto Sequence=[&](const FOAGDClipBinding& B,FName RateName,bool Sync){
  auto* Player=NewObject<UAnimGraphNode_SequencePlayer>(Graph);Graph->AddNode(Player,true,false);Player->CreateNewGuid();Player->PostPlacedNewNode();
  Player->Node.SetSequence(B.Sequence);Player->Node.SetLoopAnimation(B.Loop);
  if(Sync){Player->Node.SetGroupName(TEXT("OAGDLocomotion"));Player->Node.SetGroupMethod(EAnimSyncMethod::SyncGroup);}
  Player->AllocateDefaultPins();
  for(auto& Pin:Player->ShowPinForProperties)if(Pin.PropertyName==TEXT("PlayRate"))Pin.bShowPin=true;
  Player->ReconstructNode();Player->NodeComment=TEXT("Locomotion ")+B.Id.ToString();Player->NodePosX=-1200;Player->NodePosY=1400+200*LocomotionRow++;
  auto* V=Variable(RateName,Player->NodePosY);V->NodePosX=-1500;
  if(!Connect(V->FindPin(RateName),Player->FindPin(TEXT("PlayRate"))))return static_cast<UEdGraphPin*>(nullptr);
  return Player->FindPin(TEXT("Pose"));
 };
 auto Mix=[&](UEdGraphPin* A,UEdGraphPin* B,FName Weight){
  auto* Node=NewObject<UAnimGraphNode_TwoWayBlend>(Graph);Graph->AddNode(Node,true,false);Node->CreateNewGuid();Node->PostPlacedNewNode();
  if(auto* Field=FindFProperty<FBoolProperty>(FAnimNode_TwoWayBlend::StaticStruct(),TEXT("bAlwaysUpdateChildren")))Field->SetPropertyValue_InContainer(&Node->BlendNode,true);
  Node->AllocateDefaultPins();
  Node->NodePosX=Weight==TEXT("RunWeight")?-850:-500;Node->NodePosY=1500;
  auto* V=Variable(Weight,1800);V->NodePosX=Node->NodePosX;
  if(!Connect(A,Node->FindPin(TEXT("A")))||!Connect(B,Node->FindPin(TEXT("B")))||!Connect(V->FindPin(Weight),Node->FindPin(TEXT("Alpha"))))return static_cast<UEdGraphPin*>(nullptr);
  return Node->FindPin(TEXT("Pose"));
 };
 for(int32 I=0;I<Set->Clips.Num();++I){
  if(Set->LocomotionEnabled&&Set->Clips[I].Id==TEXT("locomotion")){
   auto Find=[&](FName Id){return Set->Clips.FindByPredicate([Id](const auto& B){return B.Id==Id;});};
   const auto* Idle=Find(TEXT("idle"));const auto* Walk=Find(TEXT("walk"));const auto* Run=Find(TEXT("run"));
   if(!Idle||!Walk||!Run)return false;
   auto* Gait=Mix(Sequence(*Walk,TEXT("WalkRate"),true),Sequence(*Run,TEXT("RunRate"),true),TEXT("RunWeight"));
   auto* Pose=Mix(Sequence(*Idle,TEXT("PlaybackRate"),false),Gait,TEXT("MoveWeight"));
   if(!Connect(Pose,Blend->FindPin(*FString::Printf(TEXT("BlendPose_%d"),I))))return false;
   if(auto* Pin=Blend->FindPin(*FString::Printf(TEXT("BlendTime_%d"),I)))Schema->TrySetDefaultValue(*Pin,FString::SanitizeFloat(BlendSeconds));
   continue;
  }
  auto* Player=NewObject<UAnimGraphNode_SequencePlayer>(Graph);Graph->AddNode(Player,true,false);Player->CreateNewGuid();Player->PostPlacedNewNode();
  Player->Node.SetSequence(Set->Clips[I].Sequence);Player->Node.SetLoopAnimation(Set->Clips[I].Loop);
  Player->AllocateDefaultPins();
  for(auto& Pin:Player->ShowPinForProperties)if(Pin.PropertyName==TEXT("PlayRate"))Pin.bShowPin=true;
  Player->ReconstructNode();Player->NodePosX=-550;Player->NodePosY=I*160;Player->NodeComment=Set->Clips[I].Id.ToString();
  if(!Connect(Player->FindPin(TEXT("Pose")),Blend->FindPin(*FString::Printf(TEXT("BlendPose_%d"),I))))return false;
  if(!Connect(Rate->FindPin(TEXT("PlaybackRate")),Player->FindPin(TEXT("PlayRate"))))return false;
  if(auto* Pin=Blend->FindPin(*FString::Printf(TEXT("BlendTime_%d"),I)))Schema->TrySetDefaultValue(*Pin,FString::SanitizeFloat(BlendSeconds));
 }
 if(Set->LayersEnabled){
  const auto& Ref=BP->TargetSkeleton->GetReferenceSkeleton();const int32 MaskRoot=Ref.FindBoneIndex(Set->UpperRoot);
  if(MaskRoot<=0||Set->LayerClips.IsEmpty())return false;
  auto Included=[&](FName Name){int32 Bone=Ref.FindBoneIndex(Name);while(Bone!=INDEX_NONE){if(Bone==MaskRoot)return true;Bone=Ref.GetParentIndex(Bone);}return false;};
  if(Set->UpperRequiredBones.IsEmpty()||Set->LowerExcludedBones.IsEmpty())return false;
  for(FName Bone:Set->UpperRequiredBones)if(!Included(Bone))return false;
  for(FName Bone:Set->LowerExcludedBones)if(Ref.FindBoneIndex(Bone)==INDEX_NONE||Included(Bone))return false;
  const auto* First=Set->Clips.FindByPredicate([Set](const auto& B){return B.Id==Set->LayerClips[0];});if(!First||!First->LayerOnly)return false;
  auto* Previous=Blend->FindPin(TEXT("Pose"));
  for(const FString Channel:{FString(TEXT("Upper")),FString(TEXT("Full"))}){
   TArray<UEdGraphPin*> Banks;
   for(int32 Bank=0;Bank<2;++Bank){
    const FString Suffix=FString::FromInt(Bank);const FName SequenceVar(*(Channel+Suffix));
    auto* Player=NewObject<UAnimGraphNode_SequencePlayer>(Graph);Graph->AddNode(Player,true,false);Player->CreateNewGuid();Player->PostPlacedNewNode();
    Player->Node.SetSequence(First->Sequence);Player->Node.SetLoopAnimation(false);
    // Each bank owns a singleton group: its clock cannot synchronize to another bank.
    Player->Node.SetGroupName(FName(*(TEXT("OAGDLayer_")+Channel.ToLower()+Suffix)));Player->Node.SetGroupMethod(EAnimSyncMethod::SyncGroup);
    Player->AllocateDefaultPins();
    for(auto& Pin:Player->ShowPinForProperties)if(Pin.PropertyName==TEXT("Sequence")||Pin.PropertyName==TEXT("PlayRate")||Pin.PropertyName==TEXT("bLoopAnimation"))Pin.bShowPin=true;
    Player->ReconstructNode();Player->NodeComment=TEXT("Layer ")+Channel+Suffix;
    for(const auto& Pair:TArray<TPair<FName,FName>>{{SequenceVar,TEXT("Sequence")},{FName(*(Channel+TEXT("Rate")+Suffix)),TEXT("PlayRate")},{FName(*(Channel+TEXT("Loop")+Suffix)),TEXT("bLoopAnimation")}}){
     auto* V=Variable(Pair.Key,2000+Bank*200);if(!Connect(V->FindPin(Pair.Key),Player->FindPin(Pair.Value)))return false;
    }
    Banks.Add(Player->FindPin(TEXT("Pose")));
   }
   auto* Pose=Mix(Banks[0],Banks[1],FName(*(Channel+TEXT("Mix"))));if(!Pose)return false;
   if(Channel==TEXT("Upper")){
    auto* Layer=NewObject<UAnimGraphNode_LayeredBoneBlend>(Graph);Graph->AddNode(Layer,true,false);Layer->CreateNewGuid();Layer->PostPlacedNewNode();
    if(Layer->Node.BlendPoses.IsEmpty())Layer->Node.AddPose();
    FBranchFilter Filter;Filter.BoneName=Set->UpperRoot;Filter.BlendDepth=1;
    Layer->Node.LayerSetup[0].BranchFilters.Add(Filter);Layer->Node.bMeshSpaceRotationBlend=false;Layer->Node.bMeshSpaceScaleBlend=false;
    Layer->AllocateDefaultPins();auto* Weight=Variable(TEXT("UpperWeight"),2500);
    if(!Connect(Previous,Layer->FindPin(TEXT("BasePose")))||!Connect(Pose,Layer->FindPin(TEXT("BlendPoses_0")))||!Connect(Weight->FindPin(TEXT("UpperWeight")),Layer->FindPin(TEXT("BlendWeights_0"))))return false;
    Previous=Layer->FindPin(TEXT("Pose"));
   }else{Previous=Mix(Previous,Pose,TEXT("FullWeight"));if(!Previous)return false;}
  }
  if(!Connect(Previous,Root->FindPin(TEXT("Result"))))return false;
 }
 if(!Set->ConstraintsJson.IsEmpty()){
  auto* Result=Root->FindPin(TEXT("Result"));if(!Result||Result->LinkedTo.Num()!=1)return false;auto* Previous=Result->LinkedTo[0];Result->BreakAllPinLinks();
  auto* Node=NewObject<UAnimGraphNode_OAGDConstraints>(Graph);Graph->AddNode(Node,true,false);Node->CreateNewGuid();Node->PostPlacedNewNode();Node->AllocateDefaultPins();
  if(!Connect(Previous,Node->FindPin(TEXT("Source")))||!Connect(Node->FindPin(TEXT("Pose")),Result))return false;
 }
 BP->bUseMultiThreadedAnimationUpdate=false;
 FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP);BP->MarkPackageDirty();
 return BP->Status!=BS_Error&&BP->GeneratedClass;
}
