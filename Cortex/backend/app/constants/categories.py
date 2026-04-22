"""Category detection from Polymarket market text.

Polymarket Gamma API does NOT return category or tags fields.
Categories are inferred from question/description text using keyword matching.

Based on Polymarket's actual category taxonomy:
Politics, Sports, Crypto, Geopolitics, Finance, Culture, Tech, AI,
Esports, Economy, Weather, Climate & Science, Health.
"""

# Ordered keyword groups for category detection.
# Each group: (normalized_category_name, [keywords to match in text])
# Order matters — first match wins.
CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    # ── AI (separate from Tech on Polymarket) ──
    ("AI", [
        "artificial intelligence", "machine learning", " llm", " gpt",
        " ai ", " ai.", " ai?", " ai,", " ai!",
        "agi", "artificial general intelligence",
        "large language model", "language model", "transformer model",
        "chatgpt", "claude ", "gemini ", "llama ", "mistral ",
        "deepseek", "grok ", "copilot", "openai", "anthropic",
        "ai model", "ai system", "ai agent", "ai regulation",
        "ai safety", "ai alignment", "ai takeover", "ai sentience",
        "ai regulation", "ai ban", "ai act",
        "neural network", "deep learning", "generative ai",
        "text-to-video", "text-to-image", "image generation",
        "ai chip", "gpu ", "tpu", "h100",
    ]),
    # ── Crypto (separate category on Polymarket) ──
    ("Crypto", [
        "bitcoin", "btc", "crypto", "cryptocurrency", "blockchain",
        "ethereum", "eth", "solana", "sol ", "dogecoin", "doge",
        "xrp", "ripple", "cardano", "ada", "polkadot", "dot",
        "binance", "bnb", "avalanche", "avax", "chainlink", "link",
        "defi", "nft", "token", "stablecoin", "usdc", "usdt",
        "dai ", "aave", "uniswap", "sushiswap",
        "web3", "metamask", "wallet", "mining", "hashrate",
        "halving", "etf ", "spot bitcoin", "bitcoin etf",
        "satoshi", "altcoin", "memecoin", "shiba", "pepe",
        "coinbase", "ftx", "binance ", "kraken",
        "decentralized", "dao", "smart contract",
        "crypto regulation", "sec crypto", "crypto ban",
        "bitcoin price", "bitcoin hits", "bitcoin reaches",
        "ethereum price", "crypto crash", "crypto bull",
    ]),
    # ── Politics (US domestic politics, elections, politicians) ──
    ("Politics", [
        # Elections & voting
        "election", "vote", "voting", "ballot", "primary", "caucus",
        "electoral college", "swing state", "battleground state",
        # Government branches
        "congress", "senate", "house of representatives", "parliament",
        "supreme court", "federal court", "appeals court",
        # Roles
        "president", "vice president", "vp ", "senator", "representative",
        "governor", "mayor", "secretary of state", "attorney general",
        "speaker of the house", "majority leader", "minority leader",
        "chief justice", "ambassador", "cabinet",
        # US politicians (current & recent)
        "trump", "biden", "harris", "vance", "obama", "clinton",
        "sanders", "aoc", "ocasio-cortez", "pelosi", "mcconnell",
        "schumer", "mcCarthy", "johnson ", "desantis", "buttigieg",
        "rubio", "cruz", "warren", "booker", "yang", "gabbard",
        "hegseth", "ramaswamy", "haley", "christie", "scott ",
        "cory booker", "josh shapiro", "gavin newsom", "wes moore",
        "zohran mamdani", "glenn youngkin", "j.b. pritzker",
        "phil murphy", "jared polis", "greg abbott", "ron desantis",
        "pete buttigieg", "tim walz", "kamala", "jd vance",
        "j.d. vance", "donald trump", "joe biden",
        # Political parties & movements
        "democrat", "republican", "democratic party", "republican party",
        "gop ", "libertarian", "green party", "independent",
        "progressive", "conservative", "moderate", "bipartisan",
        # Political events & processes
        "impeachment", "referendum", "recall", "filibuster",
        "executive order", "veto", "legislation", "bill ", "amendment",
        "subpoena", "indictment", "testify", "congressional hearing",
        "government shutdown", "debt ceiling", "budget resolution",
        # Political topics
        "abortion", "gun control", "immigration", "border wall",
        "second amendment", "first amendment", "free speech",
        "campaign finance", "lobbying", "gerrymandering",
        "political", "partisan", "bipartisan",
    ]),
    # ── Geopolitics (international relations, conflicts, foreign policy) ──
    ("Geopolitics", [
        # Countries & regions
        "ukraine", "russia", "putin", "zelensky", "kremlin",
        "china", "taiwan", "xi jinping", "ccp", "hong kong",
        "iran", "israel", "gaza", "hamas", "hezbollah",
        "north korea", "kim jong", "south korea",
        "saudi arabia", "yemen", "syria", "iraq", "afghanistan",
        "pakistan", "india", "modi",
        "european union", "eu ", "brexit", "nato", "united nations",
        "un ", "who ", "wto", "g7", "g20",
        # Conflicts & diplomacy
        "war", "ceasefire", "invasion", "military", "conflict",
        "sanction", "treaty", "diplomatic", "embassy", "ambassador",
        "nuclear", "missile", "drone strike", "airstrike",
        "peace deal", "armistice", "proxy war", "civil war",
        "geopolitical", "foreign policy", "international relations",
        "territorial", "sovereignty", "annexation",
        # Specific conflicts & situations
        "south china sea", "strait of taiwan", "black sea",
        "red sea", "suez canal", "panama canal",
        "russia-ukraine", "israel-hamas", "us-china",
        "coup", "regime change", "protest", "revolution",
        "dictator", "authoritarian", "autocracy", "democracy",
    ]),
    # ── Economy (macroeconomics, fiscal policy, economic indicators) ──
    ("Economy", [
        # Central banks & monetary policy
        "fed", "federal reserve", "interest rate", "rate cut", "rate hike",
        "powell", "jerome powell", "quantitative easing", "qe ",
        "quantitative tightening", "qt ", "monetary policy",
        # Economic indicators
        "gdp", "inflation", "cpi", "ppi", "unemployment",
        "jobs report", "nonfarm", "consumer confidence",
        "recession", "depression", "economic growth", "economic slowdown",
        "soft landing", "hard landing", "stagflation",
        # Fiscal policy
        "national debt", "deficit", "surplus", "treasury", "treasury bond",
        "government spending", "stimulus", "bailout",
        "tax cut", "tax increase", "tariff", "trade war",
        # Economic events
        "default", "debt ceiling", "credit rating", "downgrade",
        "bank run", "banking crisis", "financial crisis",
        "economic", "economy", "macroeconomic",
        "dollar", "usd", "currency", "exchange rate",
        "yen", "euro", "pound sterling", "yuan", "renminbi",
    ]),
    # ── Finance (markets, investing, corporate finance) ──
    ("Finance", [
        # Stock market
        "stock", "stock market", "sp500", "s&p 500", "dow jones",
        "nasdaq", "nyse", "wall street", "equity", "shares",
        "ipo", " spac ", "listing", "delisting",
        # Investing
        "invest", "portfolio", "hedge fund", "mutual fund",
        "etf ", "index fund", "401k", "ira ", "roth ira",
        "venture capital", "private equity", "angel investor",
        # Corporate
        "earnings", "revenue", "profit", "loss", "quarterly",
        "merger", "acquisition", "buyout", "spin-off",
        "bankruptcy", "chapter 11", "chapter 7", " layoffs",
        "ceo ", "cfo ", "coo ", "board of directors",
        "valuation", "market cap", "unicorn", "startup",
        # Banking & lending
        "bank", "credit", "loan", "mortgage", "refinance",
        "bond", "treasury yield", "corporate bond", "junk bond",
        "financial", "finance", "fintech", "payment",
        "real estate", "housing market", "home price", "rent",
        # Specific companies (finance-related context)
        "jpmorgan", "goldman sachs", "morgan stanley", "blackrock",
        "jamie dimon", "warren buffett", "berkshire",
    ]),
    # ── Sports ──
    ("Sports", [
        # Leagues
        "nfl", "nba", "mlb", "nhl", "fifa", "world cup",
        "super bowl", "ncaa", "college football", "college basketball",
        # Sports
        "football", "basketball", "baseball", "hockey", "soccer",
        "tennis", "golf", "boxing", "mma", "ufc", "wwe",
        "cricket", "rugby", "swimming", "track and field",
        "cycling", "skiing", "snowboarding", "surfing",
        # Events
        "olympics", "olympic", "wimbledon", "superbowl", "super bowl",
        "champions league", "premier league", "la liga", "bundesliga",
        "serie a", "ligue 1", "mls ", "copa america",
        "world series", "nba finals", "stanley cup",
        "march madness", "final four", "playoff", "playoffs",
        "grand slam", "masters", "us open", "french open",
        "ballon d'or", "heisman", "mvp ", "rookie of the year",
        # Teams (NFL)
        "chiefs", "49ers", "eagles", "cowboys", "patriots",
        "bills", "ravens", "bengals", "dolphins",
        # Teams (NBA)
        "lakers", "celtics", "warriors", "bulls", "knicks",
        "heat", "bucks", "nuggets", "suns", "mavericks",
        "thunder", "timberwolves", "clippers", "76ers",
        "sixers", "hawks", "magic", "cavaliers", "cavs",
        "rockets", "grizzlies", "pelicans", "spurs", "blazers",
        "trail blazers", "kings ", "jazz ", "nets", "hornets",
        "pistons", "pacers", "raptors",
        # Teams (MLB)
        "yankees", "red sox", "dodgers", "cubs", "cardinals",
        "astros", "braves", "mets", "giants",
        # Teams (NHL)
        "oilers", "panthers", "avalanche", "golden knights",
        "bruins", "maple leafs", "canadiens", "rangers",
        "blackhawks", "red wings", "penguins", "flyers",
        "dallas stars", "tampa bay lightning", "minnesota wild", "carolina hurricanes", "buffalo sabres",
        "senators", "jets ", "flames", "ducks", "coyotes",
        "sharks", "blue jackets", "predators",
        # People
        "lebron", "brady", "mahomes", "messi", "ronaldo",
        "djokovic", "federer", "nadal", "woods", "mcgregor",
        # Sports terms
        "draft", "trade", "free agency", "contract", "salary cap",
        "championship", "tournament", "season", "coach", "manager",
        "formula 1", "f1", "nascar", "indycar", "grand prix",
    ]),
    # ── Esports ──
    ("Esports", [
        "esports", "e-sports", "competitive gaming",
        "league of legends", "lol ", "worlds ", "lck", "lpl", "lcs",
        "valorant", "vct", "champions tour",
        "counter-strike", "cs2", "cs:go", "major",
        "dota 2", "ti ", "the international",
        "overwatch", "owl ", "overwatch league",
        "fortnite", "fn", "rocket league", "rlcs",
        "call of duty", "cdl", "call of duty league",
        "apex legends", "algs",
        "twitch", "streamer", "esports team",
        "t1 ", "fnatic", "g2", "cloud9", "sentinels",
        "faze", "100 thieves", "team liquid", "navi",
    ]),
    # ── Tech (general technology, not AI) ──
    ("Tech", [
        # Companies
        "apple", "google", "microsoft", "amazon", "meta ",
        "tesla", "spacex", "nvidia", "intel", "amd",
        "qualcomm", "samsung", "tsmc", "oracle", "ibm",
        "netflix", "spotify", "uber", "lyft", "doordash",
        "tiktok", "twitter", "x ", "x.com", "threads ",
        # Products
        "iphone", "ipad", "macbook", "mac ", "ipod",
        "ios ", "android ", "windows", "macos",
        "pixel", "galaxy", "surface", "kindle",
        "vision pro", "airpods", "apple watch",
        # Tech topics
        "software", "hardware", "semiconductor", "chip", "processor",
        "cloud computing", "aws ", "azure", "gcp", "google cloud",
        "saas", "paas", "iaas", "api ", "sdk",
        "cybersecurity", "data breach", "ransomware", "hack",
        "privacy", "antitrust", "monopoly", "regulation",
        "5g", "6g", "fiber", "broadband", "satellite internet",
        "starlink", "internet", "broadband",
        "robot", "robotics", "drone", "autonomous", "self-driving",
        "electric vehicle", "ev ", "evs ", "battery", "solid-state",
        "quantum computing", "quantum computer",
        "virtual reality", "vr ", "augmented reality", "ar ",
        "mixed reality", "metaverse",
        # Space
        "spacex", "nasa", "mars", "moon landing", "rocket",
        "starship", "falcon 9", "artemis",
        # Science
        "scientific", "discovery", "physics", "biology", "chemistry",
        "gene", "crispr", "genome",
        "climate change", "global warming", "renewable energy",
        "carbon", "emission", "green energy",
    ]),
    # ── Culture (entertainment, media, celebrities, social) ──
    ("Culture", [
        # Entertainment
        "movie", "film", "oscar", "academy award", "emmy", "grammy",
        "golden globe", "sag award", "cannes", "sundance",
        "netflix", "disney", "hbo", "max ", "streaming",
        "tv show", "series", "season", "episode",
        # Music
        "music", "album", "song", "band", "singer", "rapper",
        "concert", "tour", "festival", "coachella", "lollapalooza",
        "billboard", "spotify", "apple music",
        # Celebrities
        "celebrity", "actor", "actress", "director", "hollywood",
        "influencer", "youtuber", "content creator",
        "kardashian", "kim kardashian", "kylie", "kylie jenner",
        "taylor swift", "drake", "beyonce", "rihanna",
        "elon musk", "mrbeast", "logan paul", "ksi",
        "dwayne johnson", "the rock", "oprah",
        "clooney", "dicaprio", "pitt",
        # Gaming (non-esports)
        "video game", "gaming", "gta", "grand theft auto",
        "playstation", "xbox", "nintendo", "switch",
        "steam", "epic games", "roblox", "minecraft",
        # Social & culture
        "social media", "tiktok", "instagram", "snapchat",
        "podcast", "youtube", "twitch",
        "book", "novel", "author", "bestseller",
        " art ", "museum", "gallery", "fashion", "design",
        # Awards
        "award show", "people's choice", "mtv", "vma",
        # Culture topics
        "cancel culture", "woke", "diversity", "inclusion",
        "religion", "church", "pope", "vatican",
    ]),
    # ── Weather ──
    ("Weather", [
        "hurricane", "typhoon", "cyclone", "tornado",
        "earthquake", "tsunami", "volcano", "eruption",
        "flood", "drought", "wildfire", "heat wave", "heatwave",
        "blizzard", "snowstorm", "ice storm",
        "natural disaster", "disaster", "emergency",
        "fema", "evacuation", "shelter",
        "temperature", "record heat", "record cold",
        "el nino", "la nina", "weather",
    ]),
    # ── Health ──
    ("Health", [
        "health", "medical", "medicine", "hospital", "doctor",
        "disease", "cancer", "diabetes", "obesity", "mental health",
        "fda", "cdc", "vaccine", "drug", "pharma", "pharmaceutical",
        "life expectancy", "pandemic", "epidemic", "outbreak",
        "healthcare", "insurance", "medicare", "medicaid",
        "clinical trial", "approval", "fda approval",
        "treatment", "therapy", "surgery", "transplant",
        "alzheimers", "parkinsons", "heart disease", "stroke",
        "depression", "anxiety", "adhd", "autism",
        "obamacare", "aca ", "affordable care act",
        "abortion", "roe v wade", "reproductive",
        "covid", "coronavirus", "sars-cov", "variant",
        "fda ", "nih", "who ", "surgeon general",
    ]),
]

UNCATEGORIZED = "Uncategorized"


def detect_category(question: str, description: str = "") -> str:
    """Detect category from market question and description text.

    Scans text against keyword groups in priority order.
    Returns the first matching category, or 'Uncategorized'.
    """
    text = f"{question} {description}".lower()

    for category, keywords in CATEGORY_KEYWORDS:
        for keyword in keywords:
            if keyword in text:
                return category

    return UNCATEGORIZED
