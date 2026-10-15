#include "OAGDStore.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "HAL/FileManager.h"
#include "Serialization/JsonSerializer.h"
#include "GameFramework/GameUserSettings.h"
#include "Engine/Engine.h"

namespace {
 constexpr int64 Limit=2097152;
 FString Encode(const TSharedPtr<FJsonObject>& Value){FString Text;FJsonSerializer::Serialize(Value,TJsonWriterFactory<>::Create(&Text));return Text;}
 FString Hash(const FString& Value){FTCHARToUTF8 Bytes(*Value);uint8 Digest[20];FSHA1::HashBuffer(Bytes.Get(),Bytes.Length(),Digest);return BytesToHex(Digest,20).ToLower();}
 bool Fail(FString& Error,const TCHAR* Text){Error=Text;return false;}
}
bool FOAGDStore::ValidId(const FString& Value){if(Value.IsEmpty()||Value.Len()>64)return false;for(TCHAR C:Value)if(!((C>='a'&&C<='z')||(C>='0'&&C<='9')||C=='_'||C=='-'))return false;return true;}
FString FOAGDStore::Path(const FString& Slot,int32 Generation) const{return Root/(Slot+FString::Printf(TEXT(".%d.json"),Generation));}
TSharedPtr<FJsonObject> FOAGDStore::Decode(const FString& File){
 if(IFileManager::Get().FileSize(*File)>Limit)return nullptr;
 FString Text,Body,Checksum;TSharedPtr<FJsonObject> Envelope,Value;
 if(!FFileHelper::LoadFileToString(Text,*File)||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Envelope)||!Envelope.IsValid()||!Envelope->TryGetStringField(TEXT("body"),Body)||!Envelope->TryGetStringField(TEXT("sha1"),Checksum)||Hash(Body)!=Checksum)return nullptr;
 if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Body),Value)||!Value.IsValid())return nullptr;
 double Seq=0;const TSharedPtr<FJsonObject>* Data=nullptr;
 if(!Value->TryGetNumberField(TEXT("seq"),Seq)||!FMath::IsFinite(Seq)||Seq<1||Seq>9007199254740990.0||Seq!=FMath::FloorToDouble(Seq)||!Value->TryGetObjectField(TEXT("data"),Data))return nullptr;
 return Value;
}
bool FOAGDStore::Latest(const FString& Slot,TSharedPtr<FJsonObject>& Body,int32& Generation,bool& Recovered,FString& Error) const{
 Error.Reset();Body.Reset();Recovered=false;Generation=-1;
 if(!ValidId(Slot))return Fail(Error,TEXT("invalid slot id"));
 for(int32 I=0;I<2;++I){if(!IFileManager::Get().FileExists(*Path(Slot,I)))continue;auto Candidate=Decode(Path(Slot,I));if(!Candidate.IsValid()){Recovered=true;continue;}if(!Body.IsValid()||Candidate->GetNumberField(TEXT("seq"))>Body->GetNumberField(TEXT("seq"))){Body=Candidate;Generation=I;}}
 if(!Body.IsValid())return Fail(Error,Recovered?TEXT("corrupt slot"):TEXT("slot not found"));
 double Schema=0,Version=0;FString Identity;
 if(!Body->TryGetNumberField(TEXT("schema"),Schema)||Schema!=1||!Body->TryGetNumberField(TEXT("version"),Version)||Version!=DataVersion||!Body->TryGetStringField(TEXT("project"),Identity)||Identity!=Project)return Fail(Error,TEXT("incompatible schema, project or data version"));
 return true;
}
bool FOAGDStore::Read(const FString& Slot,TSharedPtr<FJsonObject>& Data,bool& Recovered,FString& Error) const{TSharedPtr<FJsonObject> Body;int32 Generation;if(!Latest(Slot,Body,Generation,Recovered,Error))return false;Data=Body->GetObjectField(TEXT("data"));return true;}
bool FOAGDStore::Write(const FString& Slot,const TSharedPtr<FJsonObject>& Data,FString& Error) const{
 if(!ValidId(Slot)||Project.IsEmpty()||DataVersion<1||!Data.IsValid())return Fail(Error,TEXT("invalid store identity or data"));
 TSharedPtr<FJsonObject> Previous;int32 Generation;bool Recovered;
 const bool Exists=Latest(Slot,Previous,Generation,Recovered,Error);
 if(!Exists&&Error!=TEXT("slot not found"))return false;
 Error.Reset();Generation=Exists?1-Generation:0;
 auto Body=MakeShared<FJsonObject>();Body->SetNumberField(TEXT("schema"),1);Body->SetStringField(TEXT("project"),Project);Body->SetNumberField(TEXT("version"),DataVersion);Body->SetNumberField(TEXT("seq"),Exists?Previous->GetNumberField(TEXT("seq"))+1:1);Body->SetObjectField(TEXT("data"),Data);
 const FString Raw=Encode(Body);auto Envelope=MakeShared<FJsonObject>();Envelope->SetStringField(TEXT("body"),Raw);Envelope->SetStringField(TEXT("sha1"),Hash(Raw));const FString Text=Encode(Envelope);
 if(FTCHARToUTF8(*Text).Length()>Limit)return Fail(Error,TEXT("save exceeds 2 MiB"));
 if(!IFileManager::Get().MakeDirectory(*Root,true))return Fail(Error,TEXT("cannot create save directory"));
 const FString Temp=Path(Slot,Generation)+TEXT(".tmp");
 if(!FFileHelper::SaveStringToFile(Text,*Temp,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)||!Decode(Temp).IsValid())return Fail(Error,TEXT("staged save readback failed"));
 if(!IFileManager::Get().Move(*Path(Slot,Generation),*Temp,true,true,false,true))return Fail(Error,TEXT("cannot commit save generation"));
 return true;
}
TSharedPtr<FJsonObject> FOAGDSettings::Defaults(){auto Value=MakeShared<FJsonObject>();Value->SetNumberField(TEXT("fps"),60);Value->SetBoolField(TEXT("vsync"),true);Value->SetNumberField(TEXT("camera_sensitivity"),1);return Value;}
bool FOAGDSettings::Validate(const TSharedPtr<FJsonObject>& Data,FString& Error){
 Error.Reset();double FPS=0,Sensitivity=0;bool VSync=false;
 if(!Data.IsValid()||Data->Values.Num()!=3||!Data->TryGetNumberField(TEXT("fps"),FPS)||!(FPS==0||FPS==30||FPS==60||FPS==120))return Fail(Error,TEXT("fps must be 0, 30, 60 or 120"));
 if(!Data->TryGetBoolField(TEXT("vsync"),VSync))return Fail(Error,TEXT("vsync must be boolean"));
 if(!Data->TryGetNumberField(TEXT("camera_sensitivity"),Sensitivity)||!FMath::IsFinite(Sensitivity)||Sensitivity<.1||Sensitivity>4)return Fail(Error,TEXT("camera sensitivity outside 0.1..4"));return true;
}
bool FOAGDSettings::Apply(const TSharedPtr<FJsonObject>& Data,FString& Error){if(!Validate(Data,Error))return false;auto* Settings=GEngine?GEngine->GetGameUserSettings():nullptr;if(!Settings)return Fail(Error,TEXT("GameUserSettings unavailable"));Settings->SetFrameRateLimit(Data->GetNumberField(TEXT("fps")));Settings->SetVSyncEnabled(Data->GetBoolField(TEXT("vsync")));Settings->ApplyNonResolutionSettings();return true;}
