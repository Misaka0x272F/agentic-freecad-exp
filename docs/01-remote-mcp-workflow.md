# The remote-MCP workflow

## Goal

Drive **FreeCAD running on a different machine** from an agent, over the
[Model Context Protocol](https://modelcontextprotocol.io), and produce real
engineering geometry rather than a toy demo.

```
┌─ agent machine ────────────────────────────┐   ┌─ CAD machine ────────────────┐
│                                            │   │                              │
│  CodeBuddy  ──stdio──▶  freecad-mcp        │   │   FreeCAD (GUI)              │
│  (LLM agent)            (MCP server,       │   │     └─ FreeCADMCP addon      │
│                          `uvx freecad-mcp  │──XML-RPC──▶  XML-RPC server     │
│                           --host HOST`)    │   │              :9875           │
│                                            │   │     (IP-allowlisted,         │
│                                            │   │      GUI-thread dispatch)    │
└────────────────────────────────────────────┘   └──────────────────────────────┘
```

Two components are involved and they are easy to confuse:

| component | runs on | role |
|---|---|---|
| `freecad-mcp` (Python package) | the **agent** machine | MCP server; translates MCP tool calls into XML-RPC |
| `FreeCADMCP` addon | the **CAD** machine, inside FreeCAD | XML-RPC server; executes code on FreeCAD's GUI thread |

## Setup

### 1. On the CAD machine

Copy `addon/FreeCADMCP` from the freecad-mcp repository into FreeCAD's addon
directory, restart FreeCAD, switch to the **MCP Addon** workbench, and in the
**FreeCAD MCP** toolbar:

1. tick **Remote Connections** (the server will bind `0.0.0.0` on next restart);
2. click **Configure Allowed IPs** and add the agent machine's address — a single
   IP is safer than a subnet. The default is `127.0.0.1` only;
3. restart the RPC server;
4. optionally tick **Auto-Start Server** so it comes up with FreeCAD.

### 2. On the agent machine

```bash
# CodeBuddy
codebuddy mcp add --scope user freecad -- uvx freecad-mcp --host <cad-host>
codebuddy mcp list          # expect: freecad ... ✓ Connected
```

`uvx` fetches and runs the published package; no clone is needed. For other MCP
clients the equivalent entry is:

```json
{
  "mcpServers": {
    "freecad": { "command": "uvx", "args": ["freecad-mcp", "--host", "<cad-host>"] }
  }
}
```

### 3. Verify before trusting

```bash
# is anything listening?
timeout 5 bash -c 'cat < /dev/null > /dev/tcp/<cad-host>/9875' && echo OPEN

# does the XML-RPC layer actually answer? (bypasses the MCP layer)
python3 -c "
import xmlrpc.client
print(xmlrpc.client.ServerProxy('http://<cad-host>:9875', allow_none=True).ping())"
```

If the first succeeds and the second reports *"Remote end closed connection
without response"*, the client IP is missing from the addon's allowlist — see
[lessons-learned A2](06-lessons-learned.md#a2-tcp-connects-but-every-xml-rpc-call-is-closed-with-no-response).

## How the work was actually done

The MCP surface used here is small: `execute_code`, `execute_code_async`,
`execute_code_headless`, `create_document`, `list_documents`, `get_rpc_status`,
`get_view`, `reload_document`. Nearly all real work went through
`execute_code` — writing FreeCAD Python directly is far more effective than
composing dozens of primitive tool calls.

A loop that worked well:

1. **Probe before building.** The first questions are always "what is actually
   available on this install?" — FreeCAD version, which workbenches and addons
   exist, which API surface is present. In this project the probe established
   that FCGear was *not* installed but `PartDesign.fcgear.involute` shipped with
   FreeCAD and could generate real involute profiles.
2. **Measure the convention, do not assume it.** The gear generator's tooth
   phase was established by measurement, twice, after the first measurement
   proved unreliable (see
   [lessons-learned C4](06-lessons-learned.md#c4-measure-gear-phase-at-the-pitch-circle-not-at-the-tip)).
3. **Build with parameters at module level** so later calls can reuse them — the
   `execute_code` namespace is persistent within a session.
4. **Verify numerically in the same breath as building.** Centre distance,
   interference volume, and the analytic volume of every cut.
5. **Keep screenshots off analytical steps** (`include_screenshot=False`) and
   take a view only when a visual is genuinely needed.

### Cost and latency habits

* Batch related geometry into one `execute_code` call; a round trip costs more
  than the extra statements.
* GUI operations run one at a time with a 90 s execution budget. Anything that
  may run for minutes (lofts, big booleans, FEM) belongs in
  `execute_code_async` with `commit()` for the document writes, or in
  `execute_code_headless`.
* `get_rpc_status` is answered off the GUI thread, so it is the tool to reach for
  when a call appears stuck.
* `execute_code_headless` runs **on the agent machine**, not the CAD machine —
  and its file paths are the agent machine's paths.

### Reproducing a remote model locally

The final models in `models/` were rebuilt from these scripts with a **local**
FreeCAD 1.0.0 (`freecadcmd`), while the originals were built on FreeCAD 1.1.0 on
the CAD machine. The verification suite passes on both; total volumes differ by
about 0.3 %, which is boolean-kernel drift between the two releases, not a
modelling difference.

| | remote build (1.1.0) | local rebuild (1.0.0) |
|---|---|---|
| single-stage total | 7747.4 cm³ | 7744.2 cm³ |
| two-stage total | 16352.6 cm³* | 16336.3 cm³ |

\* the two-stage figure shown is from the pre-fix build; see the note in
[verification](05-verification.md).

## Privacy note

The workflow uses a hostname and a LAN address, and the CAD host has a user
profile. Those are deliberately **not** recorded in this repository: placeholders
`<cad-host>` are used throughout, and the scripts contain no absolute paths or
credentials.
