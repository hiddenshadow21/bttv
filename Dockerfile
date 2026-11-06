# syntax=docker/dockerfile:1.7
# Build and export a standalone BTTV APK with one Docker command:
#   docker build --progress=plain --output type=local,dest=./dist .
# Requires the user's original Twitch 31.8.0 split bundle at ./twitch.zip.

# Hermes-decomp 0.2.4 Linux release requires glibc >= 2.39 (Ubuntu 24.04 Noble).
# Keep Java 11 for the existing Gradle 7.2 build.
FROM eclipse-temurin:11-jdk-noble AS toolchain
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git unzip zip rsync jq python3 perl \
    && rm -rf /var/lib/apt/lists/*

ENV ANDROID_SDK_HOME=/opt/android-sdk-linux \
    ANDROID_SDK_ROOT=/opt/android-sdk-linux \
    ANDROID_HOME=/opt/android-sdk-linux \
    ANDROID_SDK=/opt/android-sdk-linux \
    APKTOOL_PATH=/opt/apktool_2.9.3.jar \
    UBER_APK_SIGNER_PATH=/opt/uber-apk-signer-1.2.1.jar \
    BAKSMALI_PATH=/opt/baksmali-2.4.0.jar \
    APKEDITOR_PATH=/opt/APKEditor-1.4.9.jar \
    GRADLE_USER_HOME=/opt/gradle-home \
    DOCKER=true

WORKDIR /opt
RUN curl -fL --retry 3 \
      https://dl.google.com/android/repository/commandlinetools-linux-6858069_latest.zip \
      -o /tmp/android-cli.zip \
    && unzip -q /tmp/android-cli.zip -d /opt \
    && rm /tmp/android-cli.zip \
    && mkdir -p "$ANDROID_SDK_ROOT" \
    && yes | /opt/cmdline-tools/bin/sdkmanager \
         --sdk_root="$ANDROID_SDK_ROOT" --licenses > /dev/null
RUN yes | /opt/cmdline-tools/bin/sdkmanager \
      --sdk_root="$ANDROID_SDK_ROOT" \
      'platforms;android-30' 'build-tools;30.0.3'

RUN curl -fL --retry 3 \
      https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar \
      -o "$APKTOOL_PATH" \
    && curl -fL --retry 3 \
      https://github.com/patrickfav/uber-apk-signer/releases/download/v1.2.1/uber-apk-signer-1.2.1.jar \
      -o "$UBER_APK_SIGNER_PATH" \
    && curl -fL --retry 3 \
      https://bitbucket.org/JesusFreke/smali/downloads/baksmali-2.4.0.jar \
      -o "$BAKSMALI_PATH" \
    && curl -fL --retry 3 \
      https://github.com/REAndroid/APKEditor/releases/download/V1.4.9/APKEditor-1.4.9.jar \
      -o "$APKEDITOR_PATH"

# Use the verified Hermes 98 assembler to patch the chat row without
# decompiling/recompiling JS. Kept in the cached toolchain layer.
RUN curl -fL --retry 3 \
      https://github.com/SymbioticSec/hermes-decomp/releases/download/v0.2.4/hermes-decomp-v0.2.4-linux-x86_64.tar.gz \
      -o /tmp/hermes-decomp.tar.gz \
    && echo '6e070410432575698657b38d3497f66fd91c0c00f63880d6776703d81d99b5ac  /tmp/hermes-decomp.tar.gz' | sha256sum -c - \
    && mkdir -p /tmp/hermes-tools \
    && tar -xzf /tmp/hermes-decomp.tar.gz -C /tmp/hermes-tools \
    && hermes_bin="$(find /tmp/hermes-tools -type f -name hermes-decomp -print -quit)" \
    && test -n "$hermes_bin" \
    && install -m 0755 "$hermes_bin" /usr/local/bin/hermes-decomp \
    && hermes-decomp --help > /dev/null \
    && rm -rf /tmp/hermes-tools /tmp/hermes-decomp.tar.gz

RUN git config --global user.email 'builder@example.invalid' \
    && git config --global user.name 'BTTV Local Builder' \
    && mkdir -p "$GRADLE_USER_HOME" \
    && printf 'org.gradle.daemon=false\n' > "$GRADLE_USER_HOME/gradle.properties"

# Fetch Gradle 7.2 in a separate Docker layer. Editing mod Java/BTTV hooks
# no longer causes gradlew to download the distribution again.
WORKDIR /opt/gradle-prep
COPY mod/gradlew ./gradlew
COPY mod/gradle/ ./gradle/
RUN sed -i 's/\r$//' ./gradlew && bash ./gradlew --version

# Cache Gradle plugin resolution separately from mod source. Dependencies are
# persisted across changed-source builds in a BuildKit cache mount below.
COPY mod/build.gradle mod/settings.gradle mod/gradle.properties ./
COPY mod/app/build.gradle ./app/build.gradle
COPY mod/twitch/build.gradle ./twitch/build.gradle
COPY mod/consumer/build.gradle ./consumer/build.gradle
RUN --mount=type=cache,id=bttv-gradle-caches,target=/opt/gradle-home/caches,sharing=locked \
    bash ./gradlew help --console=plain -q

# The expensive APK decompilation depends only on the original Twitch bundle
# and setup.sh, not on the mod sources, hook code, or BTTV version metadata.
FROM toolchain AS decoded-twitch
WORKDIR /usr/build
COPY twitch.zip /repo/twitch.zip
COPY v31/setup.sh /repo/v31/setup.sh
RUN sed -i 's/\r$//' /repo/v31/setup.sh \
    && bash /repo/v31/setup.sh

# If only mod Java changes, keep the verified smali patch layer cached too.
FROM decoded-twitch AS patched-twitch
COPY v31/apply_hooks.sh v31/apply_hooks_31_8.py v31/patch_hermes_timestamps.py /repo/v31/
RUN sed -i 's/\r$//' /repo/v31/apply_hooks.sh \
    && bash /repo/v31/apply_hooks.sh

FROM patched-twitch AS builder
COPY mod/ /repo/mod/
COPY v31/build_mod.sh v31/RenamePackage.java /repo/v31/
COPY bttv.manifest.json /repo/bttv.manifest.json
# Keep /opt/gradle-home/wrapper/dists from the cached layer. Only the Gradle
# dependency cache uses a writable BuildKit mount, so source edits reuse it.
RUN --mount=type=cache,id=bttv-gradle-caches,target=/opt/gradle-home/caches,sharing=locked \
    sed -i 's/\r$//' /repo/v31/build_mod.sh \
    && bash /repo/v31/build_mod.sh

# BuildKit exports only the APK, not the intermediate image filesystem.
FROM scratch AS export
COPY --from=builder /artifact/ /
