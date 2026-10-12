#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/brown/Documents/School/NPRT/android_student_portal"
SDK_DIR="/home/brown/Android/Sdk"
BUILD_TOOLS="$SDK_DIR/build-tools/35.0.0"
PLATFORM_JAR="$SDK_DIR/platforms/android-34/android.jar"
OUT_DIR="$PROJECT_DIR/build"
FINAL_APK="/home/brown/Documents/School/NPRT/UPBS-Student-Portal.apk"

echo "==> Cleaning build directory..."
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/gen" "$OUT_DIR/obj" "$OUT_DIR/dex" "$OUT_DIR/res"

echo "==> 1. Compiling Android resources with aapt2..."
"$BUILD_TOOLS/aapt2" compile \
    --dir "$PROJECT_DIR/src/main/res" \
    -o "$OUT_DIR/res/resources.zip"

echo "==> 2. Linking manifest and resources with aapt2..."
"$BUILD_TOOLS/aapt2" link \
    -o "$OUT_DIR/unaligned.apk" \
    -I "$PLATFORM_JAR" \
    --manifest "$PROJECT_DIR/src/main/AndroidManifest.xml" \
    --java "$OUT_DIR/gen" \
    --min-sdk-version 24 \
    --target-sdk-version 34 \
    --version-code 1 \
    --version-name "1.0.0" \
    "$OUT_DIR/res/resources.zip"

echo "==> 3. Compiling Java source files with javac..."
javac -source 1.8 -target 1.8 \
    -bootclasspath "$PLATFORM_JAR" \
    -classpath "$PLATFORM_JAR" \
    -d "$OUT_DIR/obj" \
    "$OUT_DIR/gen/za/ac/spu/upbs/student/R.java" \
    "$PROJECT_DIR/src/main/java/za/ac/spu/upbs/student/MainActivity.java"

echo "==> 4. Converting JVM bytecode to Dalvik DEX with d8..."
CLASS_FILES=$(find "$OUT_DIR/obj" -name "*.class")
"$BUILD_TOOLS/d8" \
    --lib "$PLATFORM_JAR" \
    --min-api 24 \
    --output "$OUT_DIR/dex" \
    $CLASS_FILES

echo "==> 5. Packaging classes.dex into APK..."
cp "$OUT_DIR/dex/classes.dex" "$OUT_DIR/classes.dex"
(cd "$OUT_DIR" && zip -q -u unaligned.apk classes.dex)

echo "==> 6. Aligning APK on 4-byte boundaries with zipalign..."
"$BUILD_TOOLS/zipalign" -f -p 4 "$OUT_DIR/unaligned.apk" "$OUT_DIR/aligned.apk"

KEYSTORE="$PROJECT_DIR/upbs-release-key.jks"
if [ ! -f "$KEYSTORE" ]; then
    echo "==> 7. Generating signing keystore..."
    keytool -genkeypair \
        -v \
        -keystore "$KEYSTORE" \
        -alias upbs_student \
        -keyalg RSA \
        -keysize 2048 \
        -validity 10000 \
        -storepass upbs2026 \
        -keypass upbs2026 \
        -dname "CN=UPBS Student Portal, OU=NPRT630 Techno Warriors, O=Sol Plaatje University, L=Kimberley, ST=Northern Cape, C=ZA"
fi

echo "==> 8. Signing APK (v1 + v2 + v3 schemes) with apksigner..."
"$BUILD_TOOLS/apksigner" sign \
    --ks "$KEYSTORE" \
    --ks-key-alias upbs_student \
    --ks-pass pass:upbs2026 \
    --key-pass pass:upbs2026 \
    --out "$FINAL_APK" \
    "$OUT_DIR/aligned.apk"

echo "==> 9. Verifying APK signature..."
"$BUILD_TOOLS/apksigner" verify --verbose "$FINAL_APK"

mkdir -p /home/brown/Documents/School/NPRT/static/apk
cp "$FINAL_APK" /home/brown/Documents/School/NPRT/static/apk/UPBS-Student-Portal.apk

ls -lh "$FINAL_APK"
echo "==> SUCCESS: Built Waydroid-ready APK at $FINAL_APK"
