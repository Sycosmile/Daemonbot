# Daemonbot 🤖⚡

Multi-chain AI crypto Telegram bot. Inspired by RickBurpBot + Phanes.

Built by **MR SYCO** ([@Sycosmile](https://github.com/Sycosmile)) — 3MTT Cybersecurity fellow, bug bounty hunter.

[GitHub](https://github.com/Sycosmile) · [X](https://x.com/Sycosmile)

---

## Features

### Price, scan & charts
| Command | Description |
|---|---|
| `/p` `<symbol or CA>` | Real-time price, volume, MC, liquidity |
| `/scan` `<CA>` (alias `/ca`) | Full contract scan + basic risk flags |
| `/z` `<symbol or CA>` | One-line compact scan |
| `/chart` `<token>` (alias `/c`) | DexScreener chart link |
| `/trending` | CoinGecko trending tokens |
| `/th` `<CA>` | Top holders (explorer redirect) |
| `/bm` `<CA>` | BubbleMap link (holder concentration) |

### Leaderboards & calls
| Command | Description |
|---|---|
| `/lb` | Group call leaderboard (who calls the most) |
| `/ga` | ATH leaderboard — best calls by multiplier |
| `/call` `<1-5>` | Log a conviction call (reply to a scan) |
| `/calls` | Your conviction call history + live performance |
| `/clb` | Conviction call leaderboard |
| `/fc` `<symbol or CA>` | Who called this token first in the group |
| `/pnl` `<token>` | Your PNL card image for a call |
| `/gpnl` `<1d\|7d\|30d\|all>` | Group PNL summary |

### Security & AI research
| Command | Description |
|---|---|
| `/rug` `<CA>` | AI-powered rug probability score |
| `/sec` `<CA>` | Full security scan (GoPlus + Honeypot.is) |
| `/nar` `<token or CA>` | AI-generated token narrative |
| `/lore` `<token>` | AI take on a token's cultural narrative |
| `/dev` `<CA>` | Deployer wallet history (needs Etherscan/BSCScan key) |
| `/soc` `<CA>` | Find socials/website from DexScreener data |
| `/x` `@username` | Heuristic recycled-account check |
| `/gh` `owner/repo` | GitHub repo health check (stars, activity, license, pros/cons) |
| `/do` `<domain>` | WHOIS lookup — registrar, age, nameservers, scam-age flag |
| `/pf` `<mint>` | Pump.fun coin info + deployer launch history |
| `/stats` _(reply optional)_ | Hit rate + median return for a caller (median resists outlier skew) |
| `/groupburp` | Most actively called tokens in the group |
| `/best` / `/worst` `<period>` | Top gainers / losers (CoinGecko) |
| `/meta` | Trending DexScreener categories |
| `/gas` | Current ETH gas prices |
| `/summary` `[count]` | AI summary of recent group chat |

### Safety
| Command | Description |
|---|---|
| `/antiscam on\|off` | Toggle drainer/scam message auto-delete + warn (off by default, see note below) |

### AI reply tools
Reply to any message with one of these:
| Command | Description |
|---|---|
| `/eli5` | Explain it like you're 5 |
| `/explain` | Plain-language explanation with context |
| `/fact` | Fact-check the claim |
| `/translate` | Translate to (or simplify into) English |

### Alerts & macro
| Command | Description |
|---|---|
| `/alert <token> <price>` | Get pinged when a token crosses a target price |
| `/alerts` | List your active alerts |
| `/unalert <id>` | Cancel an alert |
| `/cal` | Economic calendar — needs a free Finnhub key, see below |

### Passive detection
Paste a `$TICKER` or contract address with no command, anywhere in the group, and
Daemonbot replies automatically — no `/p` needed. `.` prefix to skip a message,
`.` suffix for a compact reply, `,` suffix for a full detailed scan. Toggle
per-group with `/autodetect on|off` (default: on).

### AI chat
Mention `@YourBotUsername`, reply to one of its messages, or just DM it.

**Chains supported:** Solana, Ethereum, Base, BSC, Arbitrum, Polygon (via DexScreener)

---

## Setup

### 1. Clone & install
```bash
git clone <your-repo>
cd daemonbot
pip install -r requirements.txt
```

### 2. Create your bot
- Open Telegram → [@BotFather](https://t.me/BotFather)
- `/newbot` → follow steps → copy token

### 3. Configure env
```bash
cp .env.example .env
# Edit .env with your BOT_TOKEN and ANTHROPIC_API_KEY
```

### 4. Run
```bash
python main.py
```

### Or run with Docker
```bash
docker build -t daemonbot .
docker run -d --env-file .env -v daemonbot_data:/app/data daemonbot
```

### Run the tests
```bash
pip install -r requirements-dev.txt
pytest -v
```
CI runs this automatically on every push via `.github/workflows/ci.yml` — same
compile + import + test steps, so a `config.py`-style "bot can't even start"
bug gets caught before you ever open Telegram.

---

## Project Structure

```
daemonbot/
├── main.py                # Entry point, handler registration, alerts JobQueue
├── config.py              # All env vars + constants
├── requirements.txt
├── requirements-dev.txt   # pytest, pytest-asyncio
├── Dockerfile / .dockerignore
├── .github/workflows/ci.yml
├── pytest.ini / conftest.py
├── .env.example
├── data/                  # Auto-created — leaderboard/conviction/alerts/settings JSON (gitignored)
├── tests/                 # Pure-logic unit tests (regex, stats math, cache, scam heuristics)
├── handlers/
│   ├── commands.py        # All slash commands
│   ├── chat.py             # AI mention/reply handler
│   ├── fixlinks.py         # Social link auto-detection
│   ├── message_store.py    # Silent message logging for /summary
│   ├── autodetect.py       # Passive $ticker/CA detection
│   ├── scammer_detection.py # Drainer/scam message delete+warn (off by default)
│   └── leaderboard.py       # Placeholder — future reaction-based tracking
└── services/
    ├── crypto.py           # DexScreener + CoinGecko API (now TTL-cached)
    ├── cache.py             # Generic in-memory TTL cache
    ├── ai.py                # Claude chat personality + reply tools
    ├── rugscore.py           # AI rug score (/rug)
    ├── security_scan.py      # GoPlus + Honeypot.is scan (/sec)
    ├── scammer_detection.py  # Local heuristics + AI tie-breaker for scam links
    ├── leaderboard.py        # Call tracking + leaderboard logic
    ├── conviction.py         # Conviction call tracking (/call /calls /clb)
    ├── pnl.py / pnl_card.py  # PNL stats + image card generation
    ├── firstcaller.py        # First-caller lookup (/fc)
    ├── narrative.py          # AI token narrative (/nar)
    ├── research.py           # /lore /dev /soc /gas /groupburp /ga /best /worst /meta /bm /stats
    ├── xchecker.py           # Recycled X account heuristics (/x)
    ├── fixlinks.py           # Tweet/TikTok/Polymarket extraction + CA detection
    ├── github.py             # GitHub repo health check (/gh)
    ├── domain.py             # WHOIS lookup (/do)
    ├── pumpfun.py            # Pump.fun coin + deployer stats (/pf)
    ├── alerts.py             # Price alert storage + periodic checker
    ├── calendar.py           # Economic calendar via Finnhub (/cal)
    ├── settings.py           # Per-group toggles (autodetect, antiscam)
    └── summary.py             # AI group chat summarizer (/summary)
```

---

## APIs Used

| API | Key Required | Used For |
|---|---|---|
| [DexScreener](https://dexscreener.com/docs) | ❌ Free | Price, scan, chart, narrative |
| [CoinGecko](https://coingecko.com/api) | ❌ Free tier | Trending, gainers/losers |
| [GoPlus Security](https://gopluslabs.io) | ❌ Free | Rug score, security scan |
| [Honeypot.is](https://honeypot.is) | ❌ Free | Honeypot detection (EVM) |
| [Anthropic](https://anthropic.com) | ✅ | AI chat, rug score, narrative, lore, summary, reply tools, scam tie-breaker |
| Etherscan / BSCScan | Optional | Deployer history (`/dev`), gas (`/gas`) |
| Birdeye | Optional | Reserved for future SOL top-holders support |
| [GitHub API](https://docs.github.com/rest) | Optional | `/gh` (60/hr unauthenticated, 5,000/hr with `GITHUB_TOKEN`) |
| WHOIS (port 43) | ❌ Free | `/do` — needs outbound TCP/43, blocked on some networks |
| Pump.fun (unofficial) | ❌ Free | `/pf` — reverse-engineered, may require auth or break without notice |
| TikTok oEmbed | ❌ Free | Rich TikTok previews in fixlinks |
| Polymarket Gamma API | ❌ Free | Polymarket previews in fixlinks |
| [Finnhub](https://finnhub.io/register) | Optional (free signup) | `/cal` economic calendar |

---

## Known limitations

- **`/x` and tweet-link auto-fetch depend on public Nitter instances**, which have
  become unreliable since X tightened anti-scraping measures. Both features
  degrade gracefully (they just say "couldn't fetch") rather than crash, but
  don't expect them to work consistently without swapping in a working
  instance or a paid X API key.
- **`/dev` and `/gas`** need an Etherscan/BSCScan key in `.env` to do anything
  beyond pointing you at the explorer manually.
- **`/pf`** depends on pump.fun's unofficial, reverse-engineered API. One of
  their endpoints already shows signs of requiring auth — this could get
  walled off entirely without notice. Fails gracefully with a direct link if so.
- **`/cal`** needs a free Finnhub API key (no truly free *and* no-key economic
  calendar API exists as of writing) — shows a clear setup message without one.
- **`/antiscam`** is heuristic, not perfect. It's deliberately delete + warn
  only — it never auto-bans, because a false positive banning a real person
  is worse than one scam message slipping through for a human admin to catch.
  Expand `URGENCY_PHRASES`/`TYPOSQUAT_RE` in `services/scammer_detection.py`
  as you see real spam patterns in your own groups.
- Leaderboard, conviction, alert, and settings data are stored in local JSON
  files (`data/`) — fine for a single-instance bot, but won't survive a
  redeploy unless you persist that folder (the Dockerfile mounts it as a
  volume for exactly this reason).

---

## Adding to a Group

1. Add `@YourBotUsername` to the group
2. Give it **admin rights** (for reading messages + deleting spam — required
   for `/antiscam` to actually delete flagged messages, not just warn)
3. Use `/scan <CA>` to start logging calls to the leaderboard

---

## Roadmap

- [ ] Birdeye top holders for Solana
- [ ] Real X API integration for `/x` (current heuristics are Nitter-dependent)
- [x] Alert system (price alerts per user)
- [ ] Web dashboard (like Rick Hub)
- [ ] Multi-language support

---

## License
MIT — fork it, build on it, ship it. Just don't rug. 🤝 See [LICENSE](LICENSE).

---

Built by **MR SYCO** — [@Sycosmile](https://github.com/Sycosmile) on GitHub and X.
