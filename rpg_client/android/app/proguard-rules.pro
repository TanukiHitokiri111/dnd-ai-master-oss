# Flutter engine и плагины
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Аннотации и generics — нужны плагинам с рефлексией
-keepattributes Signature, *Annotation*, EnclosingMethod

# Известные безобидные предупреждения
-dontwarn org.conscrypt.**
-dontwarn javax.annotation.**

# Google Play Core — deferred components (не используются, но R8 требует)
-dontwarn com.google.android.play.core.**
-keep class com.google.android.play.core.** { *; }
