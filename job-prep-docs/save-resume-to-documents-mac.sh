#!/bin/bash
# Saves Sonaal Topno resume PDF to Documents/Job-Prep (Mac/Linux)
FOLDER="$HOME/Documents/Job-Prep"
mkdir -p "$FOLDER"
URL="https://raw.githubusercontent.com/Sonaal8/Data-Analysis/master/job-prep-docs/SONAAL_TOPNO_Resume.pdf"
OUT="$FOLDER/SONAAL_TOPNO_Resume.pdf"
curl -fsSL "$URL" -o "$OUT"
echo "Saved to: $OUT"
open "$FOLDER" 2>/dev/null || xdg-open "$FOLDER" 2>/dev/null || true
