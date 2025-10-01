## Contract Scraper Bot

Scrapes Pennsylvania eMarketplace upcoming procurements, traverses all pages, enriches each listing with detail text, classifies relevance for a software development company using OpenAI, posts relevant items to Discord, and stores a local snapshot for change detection. Runs on startup and then hourly.

### Prerequisites
- Python 3.11+ (tested with 3.13)
- A Discord bot invited to your server with permission to send messages in the target channel
- An OpenAI API key

### Quick start
1) Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```
2) Install dependencies
```bash
pip install -r requirements.txt
```
3) Configure environment
```bash
cp .env.example .env
# Edit .env and fill in values (see list below)
```
4) Run
```bash
python run.py
# or
python -m src.main
```

### Run with Docker + OpenVPN (container-only tunnel)
```bash
# Build the image
docker compose build

# Start the container (tunnel comes up first, then app runs)
docker compose up -d

# View logs
docker logs -f contract-scraper
```
Notes:
- Ensure your `.ovpn` file is present at `data/Windscribe-Atlanta-Mountain.ovpn` or set `OVPN_CONFIG` env to another path inside the container.
- The container needs `NET_ADMIN` and `/dev/net/tun` which are configured in `docker-compose.yml`.
- If your `.ovpn` requires credentials, set `OVPN_AUTH_USERNAME` and `OVPN_AUTH_PASSWORD` in environment (container uses a secure auth file automatically).
### Environment variables (.env)
- DISCORD_TOKEN: Bot token
- DISCORD_GUILD_ID: Server ID (enable Developer Mode → right‑click server → Copy Server ID)
- DISCORD_CHANNEL_ID: Channel ID (right‑click channel → Copy Channel ID)
- OPENAI_API_KEY: Your OpenAI API key
- OPENAI_MODEL: Model name (default: gpt-4o-mini)
- BASE_URL: Procurement search page (default: https://www.emarketplace.state.pa.us/Procurement.aspx)
- CHECK_INTERVAL_MINUTES: Interval between syncs (default: 60)
- USER_AGENT: Optional custom user agent string
- RESET_STATE_ON_START: true/false; when true, clears saved state on startup to resend everything

Do not commit your real keys. `.env` is already gitignored.

### What it does
1) Scrape and paginate: Navigates the ASP.NET postback pager to load every results page.
2) Parse listings: Extracts id, title, agency, category, status, and the details URL while ignoring pager rows.
3) Enrich: Fetches the details page and builds a de-duplicated description.
4) Classify: Uses OpenAI to determine if a listing is relevant for software development (biases toward YES when plausible).
5) Notify: Sends relevant listings to the configured Discord channel. Long descriptions are split into 1900-char parts.
6) Persist: Saves a JSON snapshot in `data/state.json` and only sends new/changed items on subsequent runs.
7) Schedule: After first run, schedules an hourly sync.

### Project structure (hexagonal)
- Domain (`src/domain`): entities (`models.py`) and ports (`ports.py`)
- Application (`src/application`): use case/service orchestration (`service.py`)
- Adapters (`src/adapters`):
  - Scraper (`scraper/emarketplace_scraper.py`)
  - Notifier (`notifier/discord_notifier.py`)
  - State repository (`state/json_state_repo.py`)
  - Classifier (`classifier/openai_classifier.py`)
- Infrastructure (`src/infrastructure`): config and environment loading
- Entrypoint: `src/main.py` (or `run.py`)

### Discord setup tips
- Invite your bot to the server with permissions to View Channel and Send Messages in the target channel.
- Developer Mode: User Settings → Advanced → toggle Developer Mode. Then right‑click to copy IDs.

### VPN Setup
This app provides a Dockerized OpenVPN tunnel so the container's outbound traffic goes through the VPN automatically. No username/password support is included.

- The container requires `NET_ADMIN` and access to `/dev/net/tun`.
- Provide an `.ovpn` config inside `data/` (already includes `Windscribe-Atlanta-Mountain.ovpn`).
- All network requests from the app will route via the VPN interface inside the container.

### Troubleshooting
- No messages sent: ensure DISCORD_* vars are correct and the bot can see the channel.
- 2000-char limit errors: handled automatically via 1900-char chunking; ensure content is not wrapped in code blocks that add extra characters.
- Too few relevant items: adjust the titles/descriptions or model; you can tweak the classifier prompt in `openai_classifier.py`.
- Fresh start: set `RESET_STATE_ON_START=true` to resend everything once, then set back to false.

### Security
Never paste real tokens/keys in chat or commit them to the repo. Keep them only in your local `.env`.
