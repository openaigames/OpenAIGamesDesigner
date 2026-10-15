#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// Single writer, two local generations. Project validates its own payload before commit.
class OAGDCORE_API FOAGDStore {
public:
 FOAGDStore(const FString& Directory,const FString& Identity,int32 Version=1):Root(Directory),Project(Identity),DataVersion(Version){}
 bool Read(const FString& Slot,TSharedPtr<FJsonObject>& Data,bool& Recovered,FString& Error) const;
 bool Write(const FString& Slot,const TSharedPtr<FJsonObject>& Data,FString& Error) const;
 FString Path(const FString& Slot,int32 Generation) const;
 static bool ValidId(const FString& Value);
private:
 FString Root,Project;int32 DataVersion;
 bool Latest(const FString& Slot,TSharedPtr<FJsonObject>& Body,int32& Generation,bool& Recovered,FString& Error) const;
 static TSharedPtr<FJsonObject> Decode(const FString& File);
};

class OAGDCORE_API FOAGDSettings {
public:
 static TSharedPtr<FJsonObject> Defaults();
 static bool Validate(const TSharedPtr<FJsonObject>& Data,FString& Error);
 static bool Apply(const TSharedPtr<FJsonObject>& Data,FString& Error);
};
