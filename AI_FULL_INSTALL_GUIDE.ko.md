# AI Full Install Guide (Korean)

This guide is for an AI assistant helping a non-developer install
`deal-intel-mcp` in the normal full mode.

Full mode is the default product path. It uses MongoDB Atlas for real deal data.
Sample mode is only a zero-config trial or demo path.

## 1. First Message To The User

Start by explaining the setup in plain language:

```text
정식 사용 기준으로는 네 가지가 필요합니다.
1. MongoDB Atlas 계정과 Free/M0 클러스터
2. Atlas 연결 문자열(MONGODB_URI)
3. Claude Desktop 또는 Codex/ChatGPT 같은 MCP 클라이언트
4. ChatGPT OAuth 또는 Anthropic/OpenAI API key 중 하나

MongoDB 없이 먼저 맛만 보려면 sample 모드도 가능하지만,
실제 팀 데이터 운용은 full 모드가 기본입니다.
```

Do not ask the user to paste secrets into chat unless they explicitly choose to.
Prefer `.env`, the MCPB configuration form, or local environment variables.

## 2. Preparation Checklist

Confirm these before running commands.

| Item | Needed For | Notes |
|---|---|---|
| Windows + PowerShell | Local setup | Current commands assume Windows PowerShell. |
| Git | Clone the repo | Required unless the user already has the repo. |
| Miniconda | Python runtime | Recommended for non-developers because it gives a stable Python path. |
| Python 3.11 conda env | Package install and MCPB config | Use a direct env Python path, not bare `python` or `py`. |
| MongoDB Atlas account | Full mode storage | Free/M0 is enough for MVP use. |
| Atlas database user | MongoDB URI | Needs read/write permission for the selected database. |
| Atlas network access | MongoDB URI | Add current IP, or use a safe temporary allowlist while testing. |
| MCP client | Chat UI | Claude Desktop MCPB is the simplest current path. |
| LLM provider | Extraction/scoring | ChatGPT OAuth, Anthropic API key, or OpenAI API key. |

## 3. Python Interpreter Path

The Python interpreter path is the full path to the `python.exe` inside the
conda environment where `deal-intel-mcp` is installed. MCPB needs this exact
path.

On Juni's current machine, the working path is:

```text
C:\Users\JuniBecky\miniconda3\envs\event-intel\python.exe
```

For a newly created `deal-intel` environment, it will usually look like:

```text
C:\Users\<you>\miniconda3\envs\deal-intel\python.exe
```

To confirm the correct path, run:

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -c "import sys; print(sys.executable)"
```

If using the existing `event-intel` environment, run:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -c "import sys; print(sys.executable)"
```

Use the printed value in the MCPB field named `Python interpreter path`.

## 4. MongoDB Atlas Setup

Guide the user through Atlas:

1. Create or open a MongoDB Atlas account.
2. Create a Free/M0 cluster.
3. Create a database user.
4. Add the user's current IP to Network Access.
5. Copy the driver connection string.
6. Replace `<password>` in the URI locally.

Tell the user:

```text
이 연결 문자열은 비밀번호가 들어간 secret입니다. 채팅창에 그대로 붙여넣지 말고,
.env 파일이나 MCPB 설정창에만 넣는 게 좋습니다.
```

## 5. Local Install

Clone and install:

```powershell
git clone <repo-url>
cd deal-intel-mcp
```

Create a conda env if needed:

```powershell
& "$HOME\miniconda3\Scripts\conda.exe" create -n deal-intel python=3.11 -y
```

Install the package:

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m pip install -e ".[dev,embedding]"
```

If the user already has the shared `event-intel` env, use:

```powershell
& "$HOME\miniconda3\envs\event-intel\python.exe" -m pip install -e ".[dev,embedding]"
```

## 6. Configure Full Mode

Use full mode for real data:

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli config switch full
```

If using the `event-intel` env, replace the Python path accordingly.

Set secrets outside chat. Options:

1. `.env` file in the repo.
2. MCPB configuration form.
3. PowerShell environment variables for the current session.

Typical `.env` entries:

```text
MONGODB_URI=<atlas-uri>
OPENAI_API_KEY=<only-if-using-openai-api>
ANTHROPIC_API_KEY=<only-if-using-anthropic>
```

For ChatGPT OAuth, run:

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli login-chatgpt
```

## 7. Doctor And Smoke Checks

Start with offline checks:

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli config doctor --offline
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli smoke-profile --profile full --offline
```

Then run live storage checks:

```powershell
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli storage-status
& "$HOME\miniconda3\envs\deal-intel\python.exe" -m deal_intel.cli mongo doctor
```

Expected direction:

- `config doctor`: no failed checks.
- `smoke-profile --profile full --offline`: pass.
- `storage-status`: MongoDB reachable.
- `mongo doctor`: indexes and schema validators visible or actionable.

## 8. Claude Desktop MCPB Settings

When the MCPB form appears, use:

| Field | Recommended Value |
|---|---|
| Python interpreter path | The conda env Python where this package is installed. |
| Storage backend | `mongo` |
| MCP tool surface | `auto` |
| MongoDB Atlas URI | User's Atlas URI, entered in the local form only. |
| LLM provider | `chatgpt_oauth` by default. |
| Anthropic API key | Only if provider is `anthropic`. |
| OpenAI API key | Only if provider is `openai_api`. |

After installing or changing MCPB settings, restart Claude Desktop.

Ask Claude/Codex to run:

```text
config_doctor 실행해서 설정 상태 확인해줘.
```

For full mode, the normal tool surface should expose the standard real-data
tools. If it shows sample mode, check the storage backend and config profile.

## 9. First Useful Questions

After setup succeeds, ask:

```text
딜 목록 보여줘.
현재 파이프라인 건강도 보여줘.
가장 위험한 딜 하나 리뷰해줘.
고객들이 가장 많이 고민한 주제는 뭐야?
이번 주 파이프라인 보고서 만들어줘.
```

## 10. When To Use Sample Mode

Use sample mode only when:

- the user wants a no-MongoDB trial,
- an AI assistant needs a quick product-shape check,
- a demo needs fictional bundled data,
- the user is not ready to create Atlas credentials.

Sample mode can still be useful for lightweight personal testing, but tell the
user that real team operation is designed around MongoDB-backed full mode.

## 11. Troubleshooting Map

| Symptom | Likely Cause | First Check |
|---|---|---|
| Claude shows sample tools only | Storage backend/profile is sample | Run `config_doctor`. |
| Mongo doctor says backend is local_sample | Config not switched to full | Run `config switch full`. |
| Mongo ping fails | URI, password, IP allowlist, or cluster state | Check Atlas connection string and Network Access. |
| LLM tools fail | OAuth expired or API key missing | Run `login-chatgpt` or check selected provider key. |
| MCP server fails to start | Wrong Python path in MCPB | Verify the interpreter path has `deal-intel-mcp` installed. |
| Korean text looks broken | Encoding/display issue | Prefer UTF-8 files and avoid copying secrets through chat. |

## 12. AI Assistant Safety Rules

- Do not store API keys, OAuth tokens, MongoDB URIs, or passwords in docs.
- Do not put setup guides in `user_docs/`; that folder is user memory.
- Do not treat sample mode as the default path for a human user.
- For destructive actions such as delete, explain dry-run and archive gates.
- For low-risk classification/taxonomy, draft a recommendation first and let
  the user correct it when needed.
