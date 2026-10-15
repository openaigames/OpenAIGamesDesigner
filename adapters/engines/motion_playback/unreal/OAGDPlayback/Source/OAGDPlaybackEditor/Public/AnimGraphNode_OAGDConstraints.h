#pragma once
#include "CoreMinimal.h"
#include "AnimGraphNode_Base.h"
#include "OAGDConstraints.h"
#include "AnimGraphNode_OAGDConstraints.generated.h"
UCLASS()
class OAGDPLAYBACKEDITOR_API UAnimGraphNode_OAGDConstraints:public UAnimGraphNode_Base {
 GENERATED_BODY()
public:
 UPROPERTY(EditAnywhere,Category=Settings) FAnimNode_OAGDConstraints Node;
 virtual FText GetNodeTitle(ENodeTitleType::Type Type)const override{return FText::FromString(TEXT("OAGD Optional Contacts"));}
 virtual FText GetMenuCategory()const override{return FText::FromString(TEXT("OAGD"));}
};
