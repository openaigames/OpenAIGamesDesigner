#pragma once
#include "CoreMinimal.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"

// Engine-independent sequence semantics. The project binds these signals to its
// own animation, audio and gameplay systems. Advance uses elapsed game seconds.
struct FActionSequenceClip {
 FString Id,Track,Asset,Kind;
 double Start=0,In=0,Out=0,Rate=1,BlendIn=0,BlendOut=0,Volume=1;
 double End()const{return Start+(Out-In)/Rate;}
};
struct FActionSequenceSignal {double Time=0;FString Kind,Id;int32 Clip=INDEX_NONE;int32 Order=0;};
class FActionSequenceRuntime {
public:
 FString Id;double Duration=0,Time=0;bool Running=false;
 TArray<FActionSequenceClip> Clips;TArray<FActionSequenceSignal> Signals;
 TFunction<void(const FActionSequenceSignal&,const FActionSequenceClip*)> OnSignal;
 bool Load(const FString& Path){
  Stop();Clips.Reset();Signals.Reset();Cursor=0;FString Text;
  TSharedPtr<FJsonObject> Root;
  if(!FFileHelper::LoadFileToString(Text,*Path)||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)||!Root.IsValid())return false;
  FString Schema;if(!Root->TryGetStringField(TEXT("schema"),Schema)||Schema!=TEXT("action-sequence/1")||!Root->TryGetStringField(TEXT("id"),Id)||!Number(Root,TEXT("duration_s"),Duration,.01,120))return false;
  const TArray<TSharedPtr<FJsonValue>> *Assets,*Input,*Events,*Windows;
  if(!Root->TryGetArrayField(TEXT("assets"),Assets)||!Root->TryGetArrayField(TEXT("clips"),Input)||!Root->TryGetArrayField(TEXT("events"),Events)||!Root->TryGetArrayField(TEXT("windows"),Windows)||Input->Num()+Events->Num()+Windows->Num()>256)return false;
  struct FAsset{FString Binding,Kind;double Duration;};TMap<FString,FAsset> Catalog;TSet<FString> Ids;
  for(auto V:*Assets){auto O=V->AsObject();FString K;FAsset A;if(!O.IsValid()||!O->TryGetStringField(TEXT("id"),K)||Catalog.Contains(K)||!O->TryGetStringField(TEXT("binding"),A.Binding)||!O->TryGetStringField(TEXT("kind"),A.Kind)||!Number(O,TEXT("duration_s"),A.Duration,.001,120))return false;Catalog.Add(K,A);}
  for(auto V:*Input){auto O=V->AsObject();FActionSequenceClip C;FString A;
   if(!O.IsValid()||!O->TryGetStringField(TEXT("id"),C.Id)||Ids.Contains(C.Id)||!O->TryGetStringField(TEXT("track"),C.Track)||!O->TryGetStringField(TEXT("asset"),A)||!Catalog.Contains(A))return false;Ids.Add(C.Id);
   auto Asset=Catalog[A];C.Asset=Asset.Binding;C.Kind=Asset.Kind;
   if(!Number(O,TEXT("start_s"),C.Start,0,Duration)||!Number(O,TEXT("source_in_s"),C.In,0,Asset.Duration)||!Number(O,TEXT("source_out_s"),C.Out,0,Asset.Duration+.0001)||!Number(O,TEXT("rate"),C.Rate,.1,4)||!Number(O,TEXT("blend_in_s"),C.BlendIn,0,120)||!Number(O,TEXT("blend_out_s"),C.BlendOut,0,120)||!Number(O,TEXT("volume"),C.Volume,0,2)||C.Out<=C.In||C.End()>Duration+.0001||C.BlendIn+C.BlendOut>C.End()-C.Start+.0001)return false;
   const int32 Index=Clips.Add(C);Add(C.Start,TEXT("clip_start"),C.Id,Index,3);
   if(C.BlendOut>0)Add(C.End()-C.BlendOut,TEXT("clip_exit"),C.Id,Index,4);
   Add(C.End(),TEXT("clip_end"),C.Id,Index,0);
  }
  for(auto V:*Events){auto O=V->AsObject();FString K;double T;if(!O.IsValid()||!O->TryGetStringField(TEXT("id"),K)||Ids.Contains(K)||!Number(O,TEXT("time_s"),T,0,Duration))return false;Ids.Add(K);Add(T,TEXT("event"),K,INDEX_NONE,2);}
  for(auto V:*Windows){auto O=V->AsObject();FString K;double A,B;if(!O.IsValid()||!O->TryGetStringField(TEXT("id"),K)||Ids.Contains(K)||!Number(O,TEXT("start_s"),A,0,Duration)||!Number(O,TEXT("end_s"),B,0,Duration)||B<=A)return false;Ids.Add(K);Add(A,TEXT("window_open"),K,INDEX_NONE,1);Add(B,TEXT("window_close"),K,INDEX_NONE,0);}
  Signals.StableSort([](const auto& A,const auto& B){return A.Time==B.Time?A.Order<B.Order:A.Time<B.Time;});return true;
 }
 void Start(){Stop();Time=0;Cursor=0;Running=true;Advance(0);}
 void Advance(double Elapsed){if(!Running||!FMath::IsFinite(Elapsed)||Elapsed<Time)return;Time=Elapsed;while(Running&&Cursor<Signals.Num()&&Signals[Cursor].Time<=Elapsed+.0000001){const auto S=Signals[Cursor++];if(S.Kind==TEXT("window_open"))OpenWindows.Add(S.Id);if(S.Kind==TEXT("window_close"))OpenWindows.Remove(S.Id);if(S.Kind==TEXT("clip_start"))Active.Add(S.Clip);if(S.Kind==TEXT("clip_end"))Active.Remove(S.Clip);if(OnSignal)OnSignal(S,Clips.IsValidIndex(S.Clip)?&Clips[S.Clip]:nullptr);}if(Elapsed>=Duration)Running=false;}
 void Stop(){Running=false;if(OnSignal){auto Windows=OpenWindows;OpenWindows.Reset();for(const auto& IdValue:Windows){FActionSequenceSignal S;S.Time=Time;S.Kind=TEXT("window_cancel");S.Id=IdValue;OnSignal(S,nullptr);}auto Copy=Active;for(int32 Index:Copy){FActionSequenceSignal S;S.Time=Time;S.Kind=TEXT("clip_cancel");S.Id=Clips[Index].Id;S.Clip=Index;OnSignal(S,&Clips[Index]);}}Active.Reset();Running=false;}
private:
 int32 Cursor=0;TSet<int32> Active;TSet<FString> OpenWindows;
 static bool Number(const TSharedPtr<FJsonObject>& O,const TCHAR* K,double& V,double Min,double Max){return O->TryGetNumberField(K,V)&&FMath::IsFinite(V)&&V>=Min&&V<=Max;}
 void Add(double T,const FString& K,const FString& IdValue,int32 C,int32 Order){FActionSequenceSignal S;S.Time=T;S.Kind=K;S.Id=IdValue;S.Clip=C;S.Order=Order;Signals.Add(S);}
};
