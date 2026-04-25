#!/usr/bin/env bash
#
# Patch mcp-remote (the npx proxy that bridges Claude Desktop to remote MCP
# servers) to handle JSON-RPC error responses gracefully on tools/list.
#
# Bug: mcp-remote 0.1.36 / 0.1.37 / 0.1.38 crashes with
#
#     TypeError: Cannot read properties of undefined (reading 'tools')
#       at transformResponseFunction (.../chunk-XXX.js:NNNN)
#
# when the server returns a JSON-RPC error response (no `result` field) for
# a request whose method was `tools/list`. mcp-remote unconditionally calls
# `res.result.tools.filter(...)` without checking if `res.result` exists.
#
# Symptom: Claude Desktop shows "no tools available" for the MCP server.
# See issue #36 for full diagnosis.
#
# This script adds a defensive guard:
#
#     if (req.method === "tools/list") {
#       if (!res.result?.tools) return res;   // ← added
#       return { ...res, result: { ...res.result, tools: res.result.tools.filter(...) } };
#     }
#
# When to run:
#   - Right after configuring Claude Desktop the first time (and opening it
#     once so npx caches mcp-remote).
#   - After clearing ~/.npm/_npx (e.g. as part of a reset).
#   - After bumping the mcp-remote version pinned in your Claude Desktop
#     config — npx will install a fresh copy and the guard is gone.
#
# Idempotent: re-running on an already-patched file is a no-op (detected via
# inserted marker comment).

set -euo pipefail

MARK="MCP_REMOTE_PATCH_DEMO"

shopt -s nullglob
files=( ~/.npm/_npx/*/node_modules/mcp-remote/dist/chunk-*.js )

if (( ${#files[@]} == 0 )); then
    cat <<'EOF' >&2
[!] No mcp-remote installs found at ~/.npm/_npx/*/node_modules/mcp-remote/

mcp-remote is downloaded by `npx` the first time Claude Desktop spawns it.
Steps:
  1. Configure Claude Desktop with this server (see README.md).
  2. Open Claude Desktop once so it spawns mcp-remote via npx.
  3. Quit Claude Desktop completely (Cmd+Q).
  4. Run this script again.
EOF
    exit 1
fi

patched=0
already=0
failed=0

for f in "${files[@]}"; do
    if grep -q "$MARK" "$f"; then
        echo "✓ already patched · $f"
        already=$((already + 1))
        continue
    fi

    if python3 - "$f" "$MARK" <<'PY'
import sys

path, mark = sys.argv[1], sys.argv[2]
with open(path) as fh:
    src = fh.read()

old = (
    '    transformResponseFunction: (req, res) => {\n'
    '      if (req.method === "tools/list") {\n'
    '        return {\n'
    '          ...res,\n'
    '          result: {\n'
    '            ...res.result,\n'
    '            tools: res.result.tools.filter('
)

new = (
    f'    transformResponseFunction: (req, res) => {{  // {mark}\n'
    '      if (req.method === "tools/list") {\n'
    '        if (!res.result?.tools) return res;\n'
    '        return {\n'
    '          ...res,\n'
    '          result: {\n'
    '            ...res.result,\n'
    '            tools: res.result.tools.filter('
)

if old not in src:
    print(f"  pattern not found in {path}", file=sys.stderr)
    sys.exit(1)

with open(path, 'w') as fh:
    fh.write(src.replace(old, new, 1))
PY
    then
        echo "✓ patched · $f"
        patched=$((patched + 1))
    else
        echo "✗ failed  · $f" >&2
        failed=$((failed + 1))
    fi
done

echo
echo "Summary: $patched patched, $already already-patched, $failed failed (total ${#files[@]})"

if (( failed > 0 )); then
    echo
    echo "[!] Some files could not be patched. The expected pattern may have changed" >&2
    echo "    in a newer mcp-remote release. Check the bundle source manually:" >&2
    echo "    grep -n 'transformResponseFunction' ~/.npm/_npx/*/node_modules/mcp-remote/dist/chunk-*.js" >&2
    exit 1
fi

if (( patched > 0 )); then
    cat <<'EOF'

To apply the patch, reload Claude Desktop:
  osascript -e 'quit app "Claude"' && sleep 2 && open -a Claude
EOF
fi
