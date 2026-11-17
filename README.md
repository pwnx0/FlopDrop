# FlopDrop — FLOP Network Community Bot

[![GitHub Repository](https://img.shields.io/badge/GitHub-pwnx0%2FFlopDrop-blue?logo=github)](https://github.com/pwnx0/FlopDrop)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Network: Devnet & Testnet](https://img.shields.io/badge/Network-Devnet%20%7C%20Testnet-green.svg)](#network-selection)

An autonomous inference task execution and activity engine designed for the **FLOP Network** decentralized AI and compute layer. 

Built from the ground up for the community:
- **Zero Proxy Overhead**: Runs directly from your native network connection.
- **Single Wallet Simplicity**: Secure, transparent single-account architecture configured via `.env`.
- **Pure Python Cryptography**: Native SS58 format 42 address derivation and Ed25519 cryptographic challenge signing without heavy binary dependencies.
- **Substrate RPC Integration**: Direct L1 node health-checks and on-chain balance verification.
- **Deep Task Builders**: Pre-configured quantitative trade evaluation (HAL-X benchmark: market structures, liquidity sweeps, stop-loss, take-profit, and risk scoring) + customizable Web3 developer questions.
- **Optional AI Synthesis**: Optional Groq/OpenAI integration to generate dynamic prompts, with a 100% deterministic local fallback when no external API key is provided.

---

## Table of Contents
1. [Important: Gateway Enrollment Status & Caps](#-important-gateway-enrollment-status--caps-faq)
2. [Quickstart Guide](#quickstart-guide)
3. [Windows One-Click Setup](#windows-one-click-setup)
4. [CLI Command Reference](#cli-command-reference)
5. [Network Selection (Devnet vs Testnet)](#network-selection)
6. [Task Builders & Custom Web3 Questions](#task-builders--custom-web3-questions)
7. [Optional AI Task Synthesis](#optional-ai-task-synthesis)
8. [Project Structure](#project-structure)
9. [License](#license)

---

## ⚠️ IMPORTANT: Gateway Enrollment Status & Caps FAQ

If you run the bot and observe one of the following messages, **the bot is working as intended**. Please read this section before asking in community channels:

### 1. `wallet_enrollment_cap_reached`
```
[WARNING] [FlopBot] Gateway enrollment cap reached. Backing off for 900s: 
Gateway enrollment cap reached: {"error":"wallet_enrollment_cap_reached","message":"The daily wallet enrollment cap is reached; retry later."}
```
* **What it means**: The FLOP Network Devnet operators maintain a strict **network-wide daily cap** on newly enrolled wallets to protect GPU inference nodes from being overloaded. When this daily quota is filled by community registrations, the gateway temporarily rejects new enrollment challenges until the daily quota resets.
* **When does it reset?**: The daily quota resets daily at **00:00 UTC** (midnight UTC).
* **What does the bot do?**: In continuous mode (`--loop`), the bot catches this error cleanly, sleeps for 900 seconds (15 minutes), and automatically retries. You do **not** need to restart the bot.

### 2. `wallet_enrollment_unavailable`
```
[WARNING] [FlopBot] Gateway enrollment cap reached: 
{"error":"wallet_enrollment_unavailable","message":"Wallet enrollment is temporarily unavailable."}
```
* **What it means**: The gateway team has temporarily paused the enrollment worker (typically during database migrations, RPC node updates, or network upgrades).
* **What does the bot do?**: Same as above—backs off safely and retries automatically without spamming the network or risking your IP address being rate-limited.

### 3. How Token Caching Works Once Enrolled
Once your wallet is admitted by the gateway, the bot automatically caches your session Bearer token in `data/bearer_cache.json` with a 24-hour expiration window.
* You only need to enroll **once every 24 hours**.
* Subsequent tasks and loop iterations reuse the active Bearer token and bypass enrollment entirely.

---

## Quickstart Guide

### 1. Clone the Repository
```bash
git clone https://github.com/pwnx0/FlopDrop.git
cd FlopDrop
```

### 2. Install Dependencies
Requires Python 3.10 or higher:
```bash
pip install -r requirements.txt
```

### 3. Configure `.env`
Copy the template configuration:
```bash
cp .env.example .env
```
*(On Windows PowerShell: `copy .env.example .env`)*

### 4. Set Up Your Wallet
You can generate a fresh Ed25519 wallet or use an existing private key:

**To generate a new wallet:**
```bash
python main.py --generate-wallet
```
This outputs your:
- **SS58 Address (Format 42)**: e.g. `5ExampleSubstrateAddress111111111111111111111111`
- **Private Key (Hex)**: 64-character raw hex seed

Open `.env` and paste your private key:
```env
FLOP_PRIVATE_KEY=your_64_char_hex_private_key_here
```

### 5. Fund Your Wallet via Faucet
The FLOP Gateway requires your wallet to hold an on-chain balance before granting inference quotas. Request tokens directly:
```bash
python main.py --faucet
```

### 6. Verify Connection & Status
Run a comprehensive diagnostic check:
```bash
python main.py --status
```
Example output:
```text
======================================================================
                  FLOP NETWORK BOT STATUS
======================================================================
  Network Mode      : DEVNET
  RPC Node URL      : https://rpc.devnet.flop.network
  Gateway API URL   : https://api.flop.network/v1
  Wallet Address    : 5ExampleSubstrateAddress111111111111111111111111
  Substrate L1 Chain: FLOP Devnet (CONNECTED)
  On-Chain Balance  : 50.0000 FLOP
  Gateway Status    : ONLINE
  Gateway Enrolled  : YES (Token active)
  Inference Model   : qwen/qwen2.5-0.5b-instruct
  AI Task Builder   : DISABLED (Combinatorial engine)
======================================================================
```

### 7. Run Inference Tasks

**Execute a single task:**
```bash
python main.py --run-once
```

**Run continuously in daemon mode:**
```bash
python main.py --loop
```

---

## Windows One-Click Setup

For Windows users, double-click **`start.bat`**:
1. Checks for Python 3.10+ (or installs it via `winget` if missing).
2. Automatically installs dependencies from `requirements.txt`.
3. Creates `.env` and prompts you to generate a wallet if you haven't yet.
4. Launches the bot interactive menu.

---

## CLI Command Reference

| Flag | Description |
| :--- | :--- |
| `--status` | Check Substrate RPC connectivity, on-chain balance, and Gateway enrollment |
| `--generate-wallet` | Generate a new Substrate SS58 address and Ed25519 private key seed |
| `--faucet` | Request free testnet tokens from the official faucet |
| `--enroll` | Manually sign gateway challenge and acquire Bearer token |
| `--run-once` | Generate and execute a single inference turn on FLOP Network |
| `--loop` | Autonomous loop: builds tasks, executes inference, and logs to SQLite |
| `--category trade` | Run quantitative trade strategy decision tasks (default) |
| `--category web3` | Run smart contract, AMM, and decentralized protocol tasks |
| `--models` | Query and display all admitted models currently served by the Gateway |

---

## Network Selection

Switch between **Devnet** and **Testnet** with a single variable in `.env`:

```env
# Set to 'devnet' or 'testnet'
FLOP_NETWORK=devnet
```

The bot automatically points to the official RPC nodes and REST gateways:

| Endpoint | Devnet Default | Testnet Default |
| :--- | :--- | :--- |
| **Substrate RPC** | `https://rpc.devnet.flop.network` | `https://rpc.testnet.flop.network` |
| **Gateway REST API** | `https://api.flop.network/v1` | `https://api.testnet.flop.network/v1` |
| **Faucet Service** | `https://faucet.flop.network/fund` | `https://faucet.testnet.flop.network/fund` |

---

## Task Builders & Custom Web3 Questions

### 1. Quantitative Trade Decision Builder (`TradeDecisionTaskBuilder`)
Generates structured market scenarios across 20+ crypto assets (BTC, ETH, SOL, NEAR, SUI, AAVE, etc.) covering:
- Technical pattern analysis (fair value gaps, order blocks, liquidity sweeps, RSI divergence).
- Invalidation / Stop-Loss specification.
- Risk scoring (1 to 10) and trade bias evaluation (LONG / SHORT / NEUTRAL).

### 2. Custom Web3 Task Builder (`Web3CustomTaskBuilder`)
To inject your own smart contract analysis, DeFi protocol questions, or governance audit tasks, open [`task_builder.py`](file:///C:/Users/ravi/Downloads/flop/task_builder.py) and extend `Web3CustomTaskBuilder`:

```python
class Web3CustomTaskBuilder(BaseTaskBuilder):
    def generate_task(self, seed: Optional[str] = None) -> BaseTask:
        # Add your custom prompt logic here
        return BaseTask(
            task_id=f"web3-{int(time.time())}",
            category="web3",
            system_prompt="You are a senior Web3 smart contract security auditor.",
            user_prompt="Analyze this Uniswap v4 hook contract for reentrancy vulnerabilities...",
        )
```
Run your custom category with:
```bash
python main.py --run-once --category web3
```

---

## Optional AI Task Synthesis

By default, the bot uses a built-in deterministic combinatorial scenario engine—no third-party API keys are needed!

If you want an external LLM (e.g. Groq, OpenAI) to generate hyper-realistic, dynamic market events before submitting them to the FLOP Gateway:

Enable in `.env`:
```env
AI_BUILDER_ENABLED=true
AI_BUILDER_PROVIDER=groq
AI_BUILDER_API_KEY=gsk_your_groq_api_key_here
AI_BUILDER_MODEL=llama-3.3-70b-versatile
```

---

## Project Structure

```
FlopDrop/
├── .env.example          # Clean configuration template
├── .gitignore            # Security ignore rules (prevents committing secrets/data)
├── requirements.txt      # Minimal, pure dependencies (cryptography, httpx, dotenv)
├── start.bat             # Windows 1-click installer and launcher
├── README.md             # Complete user documentation and gateway troubleshooting
├── config.py             # Network preset loader & environment parser
├── crypto.py             # Substrate SS58 format 42 derivation & Ed25519 signing
├── rpc.py                # Substrate JSON-RPC & Explorer balance checker
├── client.py             # FLOP Gateway API client (challenge, enrollment, inference)
├── task_builder.py       # Modular quantitative trading & Web3 prompt generators
├── ai_builder.py         # Optional AI scenario synthesizer with local fallback
├── bot.py                # Main autonomous execution loop, auto-faucet & SQLite ledger
└── main.py               # Unified CLI interface
```

---

## Local Ledger & Persistence

Every completed inference task and receipt is saved locally in `data/flop_bot.db` (SQLite):
- Task ID and timestamp
- Category and prompt summary
- FLOP inference model response
- Token consumption and FLOP fee deduction

---

## License

Released under the [MIT License](LICENSE). Built for the FLOP Network community.
