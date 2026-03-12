#!/bin/bash
# Install SadTalker for AI lip-sync avatar generation
# Run this on the RunPod GPU machine (RTX 3090)

set -e

SADTALKER_DIR="${SADTALKER_DIR:-/workspace/SadTalker}"

echo "=== Installing SadTalker for Gneva Avatar ==="

# Clone SadTalker
if [ ! -d "$SADTALKER_DIR" ]; then
    echo "Cloning SadTalker..."
    git clone https://github.com/OpenTalker/SadTalker.git "$SADTALKER_DIR"
else
    echo "SadTalker already cloned at $SADTALKER_DIR"
fi

cd "$SADTALKER_DIR"

# Install dependencies
echo "Installing Python dependencies..."
pip install -q dlib face_alignment gfpgan basicsr facexlib retinaface_detection

# Download pretrained models
echo "Downloading pretrained models..."
if [ ! -d "checkpoints" ]; then
    mkdir -p checkpoints
fi

CKPT_BASE="https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc"

for f in mapping_00109-model.pth.tar mapping_00229-model.pth.tar SadTalker_V0.0.2_256.safetensors SadTalker_V0.0.2_512.safetensors; do
    if [ ! -f "checkpoints/$f" ]; then
        echo "  Downloading $f..."
        wget -q -P checkpoints/ "$CKPT_BASE/$f" || echo "  Warning: failed to download $f"
    fi
done

# Download BFM model
if [ ! -d "checkpoints/BFM_Fitting" ]; then
    echo "  Downloading BFM models..."
    mkdir -p checkpoints/BFM_Fitting
    wget -q -P checkpoints/BFM_Fitting/ "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/BFM_Fitting.zip" || true
    cd checkpoints/BFM_Fitting && unzip -q -o BFM_Fitting.zip 2>/dev/null; cd ../..
fi

# Set environment variable
export SADTALKER_CHECKPOINT_DIR="$SADTALKER_DIR/checkpoints"

echo ""
echo "=== SadTalker installed ==="
echo "Checkpoint dir: $SADTALKER_DIR/checkpoints"
echo ""
echo "Add to your environment:"
echo "  export SADTALKER_CHECKPOINT_DIR=$SADTALKER_DIR/checkpoints"
echo "  export PYTHONPATH=\$PYTHONPATH:$SADTALKER_DIR"
