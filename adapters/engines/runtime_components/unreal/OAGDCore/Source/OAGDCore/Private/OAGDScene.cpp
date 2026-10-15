#include "OAGDScene.h"
#include "Engine/LevelStreamingDynamic.h"
#include "Misc/PackageName.h"
UOAGDSceneComponent::UOAGDSceneComponent(){PrimaryComponentTick.bCanEverTick=true;PrimaryComponentTick.bTickEvenWhenPaused=true;}
bool UOAGDSceneComponent::Stage(const FString& Package,FString& Error){
 Error.Reset();if(Staged){Error=TEXT("transition busy");return false;}
 if(!Package.StartsWith(TEXT("/Game/"))||!FPackageName::DoesPackageExist(Package)){Error=TEXT("scene package missing");return false;}
 bool Success=false;Staged=ULevelStreamingDynamic::LoadLevelInstance(this,Package,FVector::ZeroVector,FRotator::ZeroRotator,Success);
 if(!Success||!Staged){Staged=nullptr;Error=TEXT("scene load request failed");return false;}
 Ready=false;Committing=false;Deadline=FPlatformTime::Seconds()+30;Staged->SetShouldBeVisible(false);
 Staged->OnLevelLoaded.AddDynamic(this,&UOAGDSceneComponent::Loaded);Staged->OnLevelShown.AddDynamic(this,&UOAGDSceneComponent::Shown);return true;
}
void UOAGDSceneComponent::Loaded(){if(!Staged||Committing)return;Ready=true;Prepared.Broadcast(true,TEXT("ready"));}
bool UOAGDSceneComponent::Commit(FString& Error){Error.Reset();if(!Staged||!Ready||Committing){Error=TEXT("no prepared scene");return false;}Committing=true;Deadline=FPlatformTime::Seconds()+30;Staged->SetShouldBeVisible(true);return true;}
void UOAGDSceneComponent::Shown(){if(!Staged||!Committing)return;auto* Old=Current.Get();Current=Staged;Current->OnLevelLoaded.RemoveAll(this);Current->OnLevelShown.RemoveAll(this);Staged=nullptr;Ready=false;Committing=false;if(Old){Old->SetShouldBeVisible(false);Old->SetIsRequestingUnloadAndRemoval(true);}Completed.Broadcast(true,TEXT("committed"));}
void UOAGDSceneComponent::Discard(){if(Staged){Staged->OnLevelLoaded.RemoveAll(this);Staged->OnLevelShown.RemoveAll(this);Staged->SetShouldBeVisible(false);Staged->SetIsRequestingUnloadAndRemoval(true);Staged=nullptr;}Ready=false;Committing=false;}
bool UOAGDSceneComponent::Cancel(){if(!Staged||Committing)return false;Discard();Completed.Broadcast(false,TEXT("cancelled"));return true;}
void UOAGDSceneComponent::TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick){Super::TickComponent(Delta,Type,Tick);if(Staged&&FPlatformTime::Seconds()>Deadline){Discard();Completed.Broadcast(false,TEXT("scene transition timed out; previous scene retained"));}}
void UOAGDSceneComponent::EndPlay(const EEndPlayReason::Type Reason){Discard();if(Current){Current->SetShouldBeVisible(false);Current->SetIsRequestingUnloadAndRemoval(true);Current=nullptr;}Super::EndPlay(Reason);}
