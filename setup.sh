#!/usr/bin/env bash
# Installs basic preparation tools and pinned Brush. See docs/method.md for
# Python dependencies and CUDA COLMAP requirements of the native-frame workflow.
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ${1:-} != --brush-only ]]; then
  sudo apt-get update
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ffmpeg colmap
  # Ubuntu 26.04's COLMAP package currently omits this runtime dependency.
  if apt-cache show libposelib >/dev/null 2>&1; then
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libposelib
  fi
fi
mkdir -p .tools
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)
    archive=.tools/brush-app-x86_64-unknown-linux-gnu.tar.xz
    curl -fL --retry 2 --connect-timeout 20 --max-time 300 \
      https://github.com/ArthurBrussee/brush/releases/download/v0.3.0/brush-app-x86_64-unknown-linux-gnu.tar.xz \
      -o "$archive.part"
    printf '%s  %s\n' 4f0f9a8785d1951c62df26aae247c02c5bba32b00f40b06df4e1c9b867399e20 "$archive.part" | sha256sum --check
    mv -- "$archive.part" "$archive"
    tar -xf "$archive" -C .tools
    .tools/brush-app-x86_64-unknown-linux-gnu/brush_app --version
    ;;
  Linux-aarch64)
    # Thor has no upstream prebuilt Linux ARM64 Brush 0.3.0 release.
    export PATH="$HOME/.cargo/bin:$PATH"
    command -v cargo >/dev/null || { echo 'Install Rust 1.88+ (rustup), then rerun setup.sh --brush-only.' >&2; exit 1; }
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      git build-essential pkg-config libfontconfig1-dev libxkbcommon-dev libwayland-dev libssl-dev
    if [[ ! -d .tools/brush-src ]]; then
      git clone --depth 1 --branch v0.3.0 https://github.com/ArthurBrussee/brush.git .tools/brush-src
    fi
    test "$(git -C .tools/brush-src rev-parse HEAD)" = 3edecbb2fe79d3e2c87eeab85b15e0b1dd10d486
    test -z "$(git -C .tools/brush-src status --porcelain)"
    (cd .tools/brush-src && cargo build --release --locked -j "${CARGO_BUILD_JOBS:-2}")
    printf 'Use --brush %s/.tools/brush-src/target/release/brush_app\n' "$PWD"
    ;;
  *) echo 'Install Brush 0.3.0 for your platform, and pass --brush /path/to/brush_app.' >&2; exit 1 ;;
esac
