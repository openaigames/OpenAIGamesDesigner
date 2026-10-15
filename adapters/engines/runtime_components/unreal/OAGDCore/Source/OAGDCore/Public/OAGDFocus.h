#pragma once
#include "Framework/Application/SlateApplication.h"
#include "Widgets/SWidget.h"
// Optional Slate focus restoration, no game rules or menu layout ownership.
class FOAGDFocusStack {
 TArray<TWeakPtr<SWidget>> Previous;
public:
 void Push(TSharedRef<SWidget> Target){if(FSlateApplication::IsInitialized()){Previous.Add(FSlateApplication::Get().GetKeyboardFocusedWidget());FSlateApplication::Get().SetKeyboardFocus(Target,EFocusCause::SetDirectly);}}
 void Pop(){if(!Previous.IsEmpty()&&FSlateApplication::IsInitialized()){auto Widget=Previous.Pop().Pin();if(Widget.IsValid()&&Widget->GetVisibility().IsVisible())FSlateApplication::Get().SetKeyboardFocus(Widget,EFocusCause::SetDirectly);}}
 void Clear(){Previous.Reset();}
};
