#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
  cat <<EOF
Usage: $0 <preset-name|list>

Apply a GPU configuration preset to your .env file.

Commands:
  list                    List all available presets
  <preset-name>          Apply the specified preset

Examples:
  $0 list                # Show all available presets
  $0 rtx4000-1gpu        # Apply RTX 4000 single GPU preset
  $0 rtx6000-2gpu        # Apply RTX 6000 dual GPU preset

Available presets:
  rtx4000-1gpu           Single RTX 4000 Ada (20GB)
  rtx4000-2gpu           Dual RTX 4000 Ada (40GB)
  rtx6000-1gpu           Single RTX 6000 Ada (48GB)
  rtx6000-2gpu           Dual RTX 6000 Ada (96GB)
  rtx6000-4gpu           Quad RTX 6000 Ada (192GB)

After applying a preset, you must edit .env to add:
  - HUGGING_FACE_HUB_TOKEN=hf_xxx
  - FIREWALL_ID=123456
EOF
}

list_presets() {
  echo "Available GPU Configuration Presets:"
  echo ""

  for preset in "$SCRIPT_DIR"/*.env; do
    if [ -f "$preset" ]; then
      basename="${preset##*/}"
      name="${basename%.env}"

      # Extract key info from preset file
      type=$(grep "^TYPE=" "$preset" | cut -d'=' -f2 || echo "unknown")
      model=$(grep "^MODEL_ID=" "$preset" | cut -d'=' -f2 || echo "unknown")
      tp_size=$(grep "^VLLM_TENSOR_PARALLEL_SIZE=" "$preset" | cut -d'=' -f2 || echo "1")

      echo "[$name]"
      echo "  TYPE: $type"
      echo "  GPUs: ${tp_size:-1}"
      echo "  Model: $model"
      echo ""
    fi
  done

  echo "Usage: $0 <preset-name>"
  echo "Example: $0 rtx6000-2gpu"
}

apply_preset() {
  local preset_name="$1"
  local preset_file="$SCRIPT_DIR/${preset_name}.env"
  local env_file="$REPO_ROOT/.env"

  if [ ! -f "$preset_file" ]; then
    echo "Error: Preset '$preset_name' not found"
    echo ""
    echo "Available presets:"
    for p in "$SCRIPT_DIR"/*.env; do
      if [ -f "$p" ]; then
        echo "  - $(basename "${p%.env}")"
      fi
    done
    exit 1
  fi

  # Check if .env exists and has user credentials
  local has_token=false
  local has_firewall=false
  local has_region=false
  local existing_token=""
  local existing_firewall=""
  local existing_region=""

  if [ -f "$env_file" ]; then
    # Match HuggingFace tokens (hf_...) or 1Password references (op://...)
    if grep -qE "^HUGGING_FACE_HUB_TOKEN=(hf_|op://)" "$env_file" 2>/dev/null; then
      has_token=true
      existing_token=$(grep "^HUGGING_FACE_HUB_TOKEN=" "$env_file" | cut -d'=' -f2-)
    fi
    if grep -q "^FIREWALL_ID=[0-9]" "$env_file" 2>/dev/null; then
      has_firewall=true
      existing_firewall=$(grep "^FIREWALL_ID=" "$env_file" | cut -d'=' -f2)
    fi
    # Preserve existing region if it differs from preset default
    if grep -q "^REGION=" "$env_file" 2>/dev/null; then
      has_region=true
      existing_region=$(grep "^REGION=" "$env_file" | cut -d'=' -f2)
    fi
  fi

  # Copy preset to .env
  cp "$preset_file" "$env_file"
  echo "Applied preset: $preset_name"
  echo "Created: $env_file"
  echo ""

  # Re-add existing credentials if found
  if [ "$has_token" = true ] && [ -n "$existing_token" ]; then
    # macOS and Linux compatible sed
    if sed --version >/dev/null 2>&1; then
      # GNU sed (Linux)
      sed -i "s|^HUGGING_FACE_HUB_TOKEN=.*|HUGGING_FACE_HUB_TOKEN=$existing_token|" "$env_file"
    else
      # BSD sed (macOS)
      sed -i '' "s|^HUGGING_FACE_HUB_TOKEN=.*|HUGGING_FACE_HUB_TOKEN=$existing_token|" "$env_file"
    fi
    echo "✓ Preserved existing HUGGING_FACE_HUB_TOKEN"
  fi

  if [ "$has_firewall" = true ] && [ -n "$existing_firewall" ]; then
    # macOS and Linux compatible sed
    if sed --version >/dev/null 2>&1; then
      # GNU sed (Linux)
      sed -i "s|^FIREWALL_ID=.*|FIREWALL_ID=$existing_firewall|" "$env_file"
    else
      # BSD sed (macOS)
      sed -i '' "s|^FIREWALL_ID=.*|FIREWALL_ID=$existing_firewall|" "$env_file"
    fi
    echo "✓ Preserved existing FIREWALL_ID"
  fi

  if [ "$has_region" = true ] && [ -n "$existing_region" ]; then
    # Escape for sed replacement to handle special characters like '&' and '\'
    escaped_region=$(printf '%s\n' "$existing_region" | sed -e 's/[&\\|]/\\&/g')

    # macOS and Linux compatible sed
    if sed --version >/dev/null 2>&1; then
      # GNU sed (Linux)
      sed -i "s|^REGION=.*|REGION=$escaped_region|" "$env_file"
    else
      # BSD sed (macOS)
      sed -i '' "s|^REGION=.*|REGION=$escaped_region|" "$env_file"
    fi
    echo "✓ Preserved existing REGION"
  fi

  # Check what still needs to be configured
  local needs_config=false

  if ! grep -q "^HUGGING_FACE_HUB_TOKEN=hf_" "$env_file" 2>/dev/null; then
    echo "⚠ REQUIRED: Set HUGGING_FACE_HUB_TOKEN in .env"
    needs_config=true
  fi

  if ! grep -q "^FIREWALL_ID=[0-9]" "$env_file" 2>/dev/null; then
    echo "⚠ REQUIRED: Set FIREWALL_ID in .env"
    needs_config=true
  fi

  echo ""

  if [ "$needs_config" = true ]; then
    echo "Edit .env to add required credentials:"
    echo "  nano .env"
    echo ""
  fi

  # Show preset details
  echo "Preset configuration:"
  grep "^TYPE=" "$env_file" | sed 's/^/  /'
  grep "^MODEL_ID=" "$env_file" | sed 's/^/  /'

  if grep -q "^VLLM_TENSOR_PARALLEL_SIZE=" "$env_file"; then
    grep "^VLLM_TENSOR_PARALLEL_SIZE=" "$env_file" | sed 's/^/  /'
  else
    echo "  VLLM_TENSOR_PARALLEL_SIZE=1 (single GPU)"
  fi

  echo ""
  echo "Next steps:"
  if [ "$needs_config" = true ]; then
    echo "  1. nano .env  # Add credentials"
    echo "  2. ./coder up"
  else
    echo "  ./coder up"
  fi
}

main() {
  case "${1:-}" in
    list|--list|-l)
      list_presets
      ;;
    help|--help|-h|"")
      usage
      ;;
    *)
      apply_preset "$1"
      ;;
  esac
}

main "$@"
