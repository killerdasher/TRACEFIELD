#!/usr/bin/env bash
# TRACEFIELD §16 synthetic end-to-end demonstration.
#
# Fully synthetic: fictional company, fixture files generated locally,
# example.com-style URLs, no network, no real persons or incidents.
# Mirrors tests/e2e/test_demo_case.py through the real CLI binary.
set -euo pipefail

TF="${TRACEFIELD_BIN:-tracefield}"
WORK="${DEMO_WORKDIR:-$(mktemp -d /tmp/tracefield-demo.XXXXXX)}"
export TRACEFIELD_HOME="$WORK/home"
FIX="$WORK/fixtures"
OUT="$WORK/export"
mkdir -p "$TRACEFIELD_HOME" "$FIX"

banner() { printf '\n=== %s ===\n' "$*"; }

banner "SYNTHETIC DEMO — no real persons, no live targets, no network"
echo "TRACEFIELD: $($TF --version)"
echo "data root : $TRACEFIELD_HOME"
echo "workdir   : $WORK"

banner "0. doctor (local environment only)"
$TF doctor

banner "1. case create with declared purpose and scope"
$TF case create "SYNTHETIC-demo-acme-breach" \
  --purpose "SYNTHETIC demonstration of the provenance workflow" \
  --scope "local synthetic fixtures only; no real persons"

banner "2. sources: two syndicated wire copies + one distinct + one contrary"
WIRE='Acme Corp said on Monday that an internal review found unauthorized access to a customer records database. The company stated that the incident was discovered on 2026-03-01 after an alert from its monitoring provider, and that notification of affected customers began within 48 hours. No payment card data was stored in the affected system according to the statement published on the corporate website.'
DISTINCT='Regulators opened a separate inquiry into Acme Corp data-handling practices this week, according to a spokesperson for the authority. The inquiry is described as routine and unrelated to any specific incident at the company.'
CONTRARY='A timeline compiled by the outlets own review places the first discovery of the Acme Corp intrusion at 2026-03-15, contradicting the earlier corporate statement. The discrepancy remains unexplained in public filings.'

SRC_A1=$($TF source add "https://mirror-one.example/news/acme-breach" \
  --case "SYNTHETIC-demo-acme-breach" \
  --publisher "Mirror One (wire copy)" --limitations "$WIRE" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
SRC_A2=$($TF source add "https://mirror-two.example/feeds/2026/acme-breach-remix" \
  --case "SYNTHETIC-demo-acme-breach" \
  --publisher "Mirror Two (syndicated feed)" --limitations "LEAD KICKER: same story as it crossed the wire. $WIRE" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
SRC_B=$($TF source add "https://wire-service.example/exclusive/acme-regulator-inquiry" \
  --case "SYNTHETIC-demo-acme-breach" \
  --publisher "Wire Service (exclusive)" --limitations "$DISTINCT" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
SRC_C=$($TF source add "https://outlet.example/timeline/acme-intrusion-dates" \
  --case "SYNTHETIC-demo-acme-breach" \
  --publisher "Outlet Review (contrary timeline)" --limitations "$CONTRARY" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "sources: a1=$SRC_A1 a2=$SRC_A2 b=$SRC_B c=$SRC_C"

banner "3. evidence attach (SHA-256, immutable 0400 copies) with excerpts"
printf '%s' "$WIRE" > "$FIX/article-a1.txt"
printf '%s' "$WIRE" > "$FIX/article-a2.txt"
printf '%s' "$DISTINCT" > "$FIX/article-b.txt"
printf '%s' "$CONTRARY" > "$FIX/timeline-c.txt"
EV_A1=$($TF evidence attach "$FIX/article-a1.txt" --case "SYNTHETIC-demo-acme-breach" \
  --source "$SRC_A1" --excerpt "The incident was discovered on 2026-03-01 after an alert." --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
EV_A2=$($TF evidence attach "$FIX/article-a2.txt" --case "SYNTHETIC-demo-acme-breach" \
  --source "$SRC_A2" --excerpt "The incident was discovered on 2026-03-01 after an alert." --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
EV_B=$($TF evidence attach "$FIX/article-b.txt" --case "SYNTHETIC-demo-acme-breach" \
  --source "$SRC_B" --excerpt "Regulators opened the inquiry this week; no date given for any incident discovery." --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
EV_C=$($TF evidence attach "$FIX/timeline-c.txt" --case "SYNTHETIC-demo-acme-breach" \
  --source "$SRC_C" --excerpt "The first discovery of the intrusion is placed at 2026-03-15." --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "evidence: $EV_A1 $EV_A2 $EV_B $EV_C"

banner "4. metadata-bearing fixtures: GPS JSON + generated PNG"
cat > "$FIX/device-metadata.json" <<'EOF'
{
  "device": "field-camera-01",
  "captured_at": "2026-10-16T12:00:00Z",
  "GPSCoordinates": "51.507400, -0.127800",
  "GPSLatitude": "51.507400",
  "GPSLongitude": "-0.127800",
  "note": "synthetic fixture; coordinates are a public landmark"
}
EOF
python3 - "$FIX/fixture.png" <<'EOF'
import struct, sys, zlib
def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
idat = zlib.compress(b"\x00\xff\x00\x00")
open(sys.argv[1], "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))
EOF
$TF evidence attach "$FIX/device-metadata.json" --case "SYNTHETIC-demo-acme-breach"
$TF evidence attach "$FIX/fixture.png" --case "SYNTHETIC-demo-acme-breach"
$TF observation add --case "SYNTHETIC-demo-acme-breach" --tool "manual-fixture-gen" \
  --summary "generated synthetic fixtures for the demo case" --evidence "$EV_A1"

banner "5. claim + relations (analyst review required before anything counts)"
CLAIM=$($TF claim add --case "SYNTHETIC-demo-acme-breach" \
  --text "The Acme Corp breach was discovered on 2026-03-01." --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
rel() { # from to-type evidence rationale -> relation id
  $TF relation add --case "SYNTHETIC-demo-acme-breach" --from "$1" --to "$CLAIM" \
    --type "$2" --evidence "$3" --rationale "$4" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
}
REL_A1=$(rel "$SRC_A1" supports "$EV_A1" "wire copy text carries the discovery date")
REL_A2=$(rel "$SRC_A2" corroborates "$EV_A2" "syndicated copy of the same wire story")
REL_B=$(rel "$SRC_B" supports "$EV_B" "distinct reporting consistent with the claim")
REL_C=$(rel "$SRC_C" contradicts "$EV_C" "contrary timeline places discovery on 2026-03-15")
echo "claim: $CLAIM"
echo "relations: $REL_A1 $REL_A2 $REL_B $REL_C (all start unreviewed)"

banner "6. origin clustering — syndicated copies must merge (origin-r3)"
$TF analyze origins --case "SYNTHETIC-demo-acme-breach"

banner "7. contradiction candidates — dates from excerpts, severity=candidate"
$TF analyze contradictions --case "SYNTHETIC-demo-acme-breach"

banner "8. analyst reviews the three supporting relations -> confirmed"
$TF relation review "$REL_A1" --state confirmed
$TF relation review "$REL_A2" --state confirmed
$TF relation review "$REL_B" --state confirmed
echo "--- assessment BEFORE confirming the contradiction (reproducible twice) ---"
$TF analyze claim "$CLAIM" --case "SYNTHETIC-demo-acme-breach"
$TF analyze claim "$CLAIM" --case "SYNTHETIC-demo-acme-breach"
echo "--- confirm the contradiction -> CONTESTED, then set it back to unreviewed ---"
$TF relation review "$REL_C" --state confirmed
$TF analyze claim "$CLAIM" --case "SYNTHETIC-demo-acme-breach"
$TF relation review "$REL_C" --state unreviewed

banner "9. hash-chained analysis events verify"
$TF analyze events --case "SYNTHETIC-demo-acme-breach"

banner "10. report (Markdown) — links, IDs, digests, rule versions, caveats"
$TF report "SYNTHETIC-demo-acme-breach" --format markdown

banner "11. privacy-aware export: SENSITIVE_METADATA lists keys, never values"
$TF case-export "SYNTHETIC-demo-acme-breach" --output "$OUT"
echo "--- SENSITIVE_METADATA.txt (advisory; coordinate VALUES are not copied) ---"
cat "$OUT/SENSITIVE_METADATA.txt"

banner "12. manifest verifies, then a tampered byte is detected"
$TF case-verify "$OUT"
echo "--- tamper: append one byte to an exported evidence file (expected failure) ---"
TARGET=$(find "$OUT/evidence" -type f | head -1)
printf 'X' >> "$TARGET"
set +e
$TF case-verify "$OUT"
VERIFY_CODE=$?
set -e
echo "case-verify exit code after tamper: $VERIFY_CODE (1 = detected, as designed)"

banner "DEMO COMPLETE — synthetic case only; no real data was used"
