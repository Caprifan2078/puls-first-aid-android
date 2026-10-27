# ПУЛЬС: Android APK

`qa/bootstrap` builds an independent lightweight offline Android application with 16 first-aid topics, two languages and symptom search. It is **not** the full offline-media edition and **not medically certified**.

The GitHub Actions workflow assembles a real debug APK and confirms installation, foreground launch and WebView rendering on an Android 35 emulator before publishing the APK artifact `PULS-Android-APK-Tested`.

If all three offline media ZIP archives are uploaded to this branch, the workflow instead restores the full existing content and checks its integrity before compiling.

Don't uninstall older PULS versions: this build uses a separate package name and keeps no user data shared with them.
