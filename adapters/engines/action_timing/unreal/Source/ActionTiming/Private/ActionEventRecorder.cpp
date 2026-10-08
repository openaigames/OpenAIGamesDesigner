#include "ActionEventRecorder.h"
#include "Modules/ModuleManager.h"
#include "HAL/PlatformTime.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/EngineVersion.h"
#include "Serialization/JsonSerializer.h"
#include "ProfilingDebugging/MiscTrace.h"

IMPLEMENT_MODULE(FDefaultModuleImpl, ActionTiming)
namespace {
bool ValidText(const FString& S) { if (S.TrimStartAndEnd().IsEmpty() || S.Len()>300) return false; for (TCHAR C:S) if(C<32) return false; return true; }
bool ValidToken(const FString& S) { if(S.IsEmpty() || S.Len()>120) return false; for(TCHAR C:S) if(!((C>='a'&&C<='z')||(C>='A'&&C<='Z')||(C>='0'&&C<='9')||C=='.'||C=='_'||C==':'||C=='/'||C=='-')) return false; return true; }
}
bool UActionEventRecorder::StartRecording(const FString& Action,const FString& Revision,const FString& Source,const FString& InputMode,const FString& InputDescription) {
    if(!IsInGameThread() || Active || !ValidText(Action)||!ValidText(Revision)||!ValidText(Source)||!ValidText(InputDescription)) return false;
    if(InputMode!=TEXT("human")&&InputMode!=TEXT("software")&&InputMode!=TEXT("mixed")&&InputMode!=TEXT("unknown")) return false;
    ActionName=Action;BuildRevision=Revision;CaptureSource=Source;Mode=InputMode;Input=InputDescription;
    Events.Reset();Counts.Reset();Dropped=0;LastPath.Reset();StartSeconds=FPlatformTime::Seconds();Active=true;return true;
}
bool UActionEventRecorder::RecordEvent(const FString& Track,const FString& EventName,double UncertaintySeconds) {
    if(!IsInGameThread()||!Active||!ValidToken(Track)||!ValidToken(EventName)||!FMath::IsFinite(UncertaintySeconds)||UncertaintySeconds<0) return false;
    if(Events.Num()>=10000){++Dropped;return false;}
    int32& N=Counts.FindOrAdd(Track+TEXT("\n")+EventName);++N;
    FString Id=EventName+TEXT("#")+FString::FromInt(N);
    Events.Add({Track,Id,FPlatformTime::Seconds()-StartSeconds,UncertaintySeconds});
    TRACE_BOOKMARK(TEXT("ActionTiming %s %s %s"),*ActionName,*Track,*Id);
    return true;
}
FString UActionEventRecorder::StopAndSave(bool Complete) {
    if(!IsInGameThread()||!Active)return LastPath;
    double Duration=FPlatformTime::Seconds()-StartSeconds;Active=false;
    auto Root=MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("schema"),TEXT("action-events/1"));Root->SetStringField(TEXT("engine"),TEXT("unreal"));
    Root->SetStringField(TEXT("engine_version"),FEngineVersion::Current().ToString());Root->SetStringField(TEXT("clock"),TEXT("monotonic_seconds"));
    Root->SetStringField(TEXT("action"),ActionName);Root->SetStringField(TEXT("revision"),BuildRevision);Root->SetStringField(TEXT("source"),CaptureSource);
    Root->SetStringField(TEXT("input_mode"),Mode);Root->SetStringField(TEXT("input_description"),Input);
    Root->SetNumberField(TEXT("zero_s"),0);Root->SetNumberField(TEXT("duration_s"),Duration);Root->SetBoolField(TEXT("complete"),Complete);Root->SetNumberField(TEXT("dropped_events"),Dropped);
    TArray<TSharedPtr<FJsonValue>> Rows;
    for(const auto& E:Events){auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("track"),E.Track);Row->SetStringField(TEXT("id"),E.Id);Row->SetNumberField(TEXT("t_s"),E.Time);Row->SetNumberField(TEXT("uncertainty_s"),E.Uncertainty);Rows.Add(MakeShared<FJsonValueObject>(Row));}
    Root->SetArrayField(TEXT("events"),Rows);
    FString Json;FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Json));
    FString Dir=FPaths::ProjectSavedDir()/TEXT("ActionTiming");IFileManager::Get().MakeDirectory(*Dir,true);
    FString Path=Dir/(FGuid::NewGuid().ToString(EGuidFormats::Digits)+TEXT(".json"));
    if(!FFileHelper::SaveStringToFile(Json,*Path,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)){UE_LOG(LogTemp,Error,TEXT("Action timing recording could not be saved"));return FString();}
    LastPath=FPaths::ConvertRelativePathToFull(Path);UE_LOG(LogTemp,Display,TEXT("ACTION_TIMING_SAVED %s"),*LastPath);return LastPath;
}
void UActionEventRecorder::EndPlay(const EEndPlayReason::Type Reason){if(Active)StopAndSave(false);Super::EndPlay(Reason);}
