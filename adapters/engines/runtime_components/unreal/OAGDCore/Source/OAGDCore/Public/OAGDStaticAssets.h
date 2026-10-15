#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OAGDStaticAssets.generated.h"
UCLASS()
class OAGDCORE_API UOAGDStaticAssets : public UBlueprintFunctionLibrary {
 GENERATED_BODY()
public:
 UFUNCTION(BlueprintCallable) static FString InspectMesh(class UStaticMesh* Mesh);
 UFUNCTION(BlueprintCallable) static bool GeometryMatches(class AOAGDGeometry* Actor,const FString& RecordJson);
};
