#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OAGDPlaybackBuilder.generated.h"
UCLASS()
class OAGDPLAYBACKEDITOR_API UOAGDPlaybackBuilder : public UBlueprintFunctionLibrary {
 GENERATED_BODY()
public:
 // Fill a NEW, empty AnimBlueprint with editable native sequence and blend nodes.
 UFUNCTION(BlueprintCallable,Category="OAGD") static bool BuildGraph(class UAnimBlueprint* Blueprint,class UOAGDPlaybackSet* Bindings,float BlendSeconds);
};
