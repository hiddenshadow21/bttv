# Standalone forensic decompiler: never invokes the BTTV APK builder.
# Build context: v31/diagnostics/decompile
FROM eclipse-temurin:17-jdk-noble
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip python3 \
    && rm -rf /var/lib/apt/lists/*

# Fixed upstream releases and SHA-256 digests.
RUN mkdir -p /opt/tools /opt/jadx \
    && curl -fL --retry 3 \
      https://github.com/iBotPeaches/Apktool/releases/download/v2.12.1/apktool_2.12.1.jar \
      -o /opt/tools/apktool.jar \
    && echo "66cf4524a4a45a7f56567d08b2c9b6ec237bcdd78cee69fd4a59c8a0243aeafa  /opt/tools/apktool.jar" | sha256sum -c - \
    && curl -fL --retry 3 \
      https://github.com/skylot/jadx/releases/download/v1.5.3/jadx-1.5.3.zip \
      -o /tmp/jadx.zip \
    && echo "8280f3799c0273fe797a2bcd90258c943e451fd195f13d05400de5e6451d15ec  /tmp/jadx.zip" | sha256sum -c - \
    && unzip -q /tmp/jadx.zip -d /opt/jadx \
    && chmod +x /opt/jadx/bin/jadx \
    && rm /tmp/jadx.zip

COPY decompile.py /usr/local/bin/decompile-twitch.py
WORKDIR /work
ENTRYPOINT ["python3", "/usr/local/bin/decompile-twitch.py"]
