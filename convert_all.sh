#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_DIR="${1:-"$SCRIPT_DIR/inputs"}"
OUTPUT_DIR="${2:-"$SCRIPT_DIR/outputs"}"

if [[ ! -d "$INPUT_DIR" ]]; then
  echo "Input directory '$INPUT_DIR' does not exist." >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

shopt -s nullglob
pdf_files=("$INPUT_DIR"/*.pdf "$INPUT_DIR"/*.PDF)
shopt -u nullglob

if [[ ${#pdf_files[@]} -eq 0 ]]; then
  echo "No PDF files found in '$INPUT_DIR'."
  exit 0
fi

for input_file in "${pdf_files[@]}"; do
  filename="$(basename "$input_file")"
  output_file="$OUTPUT_DIR/$filename"
  echo "Converting '$filename'..."
  python "$SCRIPT_DIR/labels_fix.py" "$input_file" "$output_file"
  rm -f "$input_file"
  echo "Saved to '$output_file' and removed original."
done

echo "All conversions completed."
