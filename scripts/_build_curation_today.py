import json, subprocess, os

run_dir = subprocess.check_output(["python", "scripts/run_dir.py"], text=True).strip()
items = json.load(open(os.path.join(run_dir, "digest_items.json")))
urls = [i["url"] for i in items]
urlset = set(urls)

U = {i["url"]: i for i in items}

# ---- HEAD ----
tldr_order = [
    "https://simonwillison.net/2026/Aug/11/stealing-reasoning-traces/#atom-everything",
    "https://techcrunch.com/2026/08/11/googles-gemini-app-surges-to-one-billion-users/",
    "https://apnews.com/article/trump-ai-regulation-executive-order-state-laws-9cb4dd1bc249e404260b3dc233217388",
    "https://www.wired.com/story/a-zoom-screen-sharing-bug-let-anyone-take-over-other-devices-on-a-call/",
    "https://www.bbc.co.uk/news/articles/cn0nww2qlp7o?at_medium=RSS&at_campaign=rss",
    "https://www.bloomberg.com/news/articles/2026-08-12/ai-coding-startup-lovable-raises-400-million-at-13-3-billion-valuation",
]

tldr_blurbs = {
    tldr_order[0]: "A paper shows encrypted chain-of-thought from OpenAI, Anthropic, and Google can be replayed and jailbroken to recover hidden reasoning.",
    tldr_order[1]: "Google says the Gemini app now has a billion users, a scale claim worth watching against actual engagement.",
    tldr_order[2]: "Trump signs an executive order aimed at blocking state AI regulations, escalating a federal versus state fight.",
    tldr_order[3]: "A Zoom screen-sharing bug let a caller take control of other participants' devices before it was patched.",
    tldr_order[4]: "An AI agent booked a gym pilates slot for its user by exploiting the booking flow, a small but concrete agent-in-the-wild case.",
    tldr_order[5]: "Lovable raised 400 million dollars at a 13.3 billion valuation, one of the larger AI coding rounds this cycle.",
}

head = {"subtitle": "", "tldr_order": tldr_order, "tldr_blurbs": tldr_blurbs}
head["subtitle"] = (
    "Policy dominates today: Trump moves to preempt state AI rules while Sanders and EU regulators push the other way. "
    "Research on stealing reasoning traces lands alongside big funding rounds for Lovable and CoreWeave."
)

# ---- ITEM OVERLAYS ----
# section options news: models, safety, projects, funding, tools, opensource
O = {}
def add(url, title, summary, themes, section):
    O[url] = {"title": title, "summary": summary, "themes": themes, "section": section}

add("https://simonwillison.net/2026/Aug/11/stealing-reasoning-traces/#atom-everything",
    "Stealing Reasoning Traces from Proprietary LLM APIs",
    "A paper shows the encrypted chain-of-thought that OpenAI, Anthropic, and Google return can be replayed across sessions and models, then jailbroken through a weaker sibling to recover hidden reasoning.",
    ["safety","models"], "safety")
add("https://www.bbc.co.uk/news/articles/cn0nww2qlp7o?at_medium=RSS&at_campaign=rss",
    "AI Agent Books a Pilates Slot by Gaming the Gym System",
    "An AI agent secured a class booking for its user by working the gym's sign-up flow, a concrete if minor example of agents acting on real-world systems.",
    ["agents"], "tools")
add("https://www.wsj.com/tech/ai/is-ai-smarter-than-humans-cyborg-956e0f0e",
    "Is AI Cannibalizing Human Intelligence",
    "An argument that heavy reliance on AI erodes the human skills it draws on, with suggestions for keeping people in the loop.",
    ["models"], "models")
add("https://www.bloomberg.com/company/stories/bloomberg-law-blaw-uses-ai-machine-learning-prove-case/",
    "Bloomberg Law Uses Machine Learning for Legal Research",
    "A vendor writeup on how Bloomberg Law applies machine learning to legal citation and case analysis.",
    ["enterprise"], "funding")
add("https://apnews.com/article/bernie-sanders-ai-public-ownership-57b9f20d96490083e2749adba0f13977",
    "Sanders Proposes Public Ownership of AI Companies",
    "Bernie Sanders unveiled a plan for public stakes in AI firms, framing frontier labs as infrastructure that should not be privately controlled.",
    ["policy"], "safety")
add("https://apnews.com/article/eu-ai-regulation-deepfakes-hacking-f4fcee1f9750e2b32cdf26ad73ee5ec2",
    "EU Begins Crackdown on AI Risks",
    "European regulators started enforcement targeting deepfakes and AI-enabled hacking under the bloc's rules.",
    ["policy"], "safety")
add("https://apnews.com/article/ai-regulation-state-moratorium-congress-39d1c8a0758ffe0242283bb82f66d51a",
    "House Republicans Push 10-Year Ban on State AI Rules",
    "A House measure would bar states from regulating AI for a decade, part of a broader federal preemption effort.",
    ["policy"], "safety")
add("https://www.reuters.com/business/ibm-together-ai-ink-240-million-deal-nvidia-powered-ai-inference-cluster-2026-08-11/",
    "IBM and Together AI Sign 240 Million Dollar Inference Deal",
    "IBM and Together AI agreed to a 240 million dollar deal for an Nvidia-powered inference cluster.",
    ["funding","inference","hardware"], "funding")
add("https://www.reuters.com/world/china/major-ai-models-glance-2026-07-08/",
    "Major AI Offerings at a Glance",
    "A reference roundup of the current major model offerings from the leading labs.",
    ["models"], "models")
add("https://apnews.com/article/ai-job-losses-education-training-929986c149d415cd2ef4dc3eaf66ca8c",
    "New Group Aims to Help Workers Adapt to AI Job Losses",
    "A coalition launched to fund retraining and support for workers displaced by AI automation.",
    ["policy","enterprise"], "safety")
add("https://apnews.com/article/data-centers-ai-electricity-sanders-aoc-65651bd28c3d911d18eeb46cd54f4c75",
    "Progressives Push AI Data Center Moratorium Bill",
    "Sanders and Ocasio-Cortez backed a bill to pause new AI data centers over electricity and cost concerns.",
    ["policy","hardware"], "safety")
add("https://apnews.com/article/trump-ai-regulation-executive-order-state-laws-9cb4dd1bc249e404260b3dc233217388",
    "Trump Signs Order to Block State AI Regulation",
    "An executive order directs the federal government to challenge state AI laws, setting up a preemption fight with statehouses.",
    ["policy"], "safety")
add("https://www.wsj.com/tech/ai/ai-chatbot-in-person-social-interactions-d1cb6831",
    "Young Adults Are Letting AI Do Their Talking",
    "A look at younger users leaning on chatbots to draft messages and manage social interactions.",
    ["apps"], "models")
add("https://www.wired.com/story/a-zoom-screen-sharing-bug-let-anyone-take-over-other-devices-on-a-call/",
    "Zoom Screen-Sharing Bug Allowed Device Takeover",
    "A now-patched Zoom flaw let a caller take control of other participants' devices during screen sharing.",
    ["safety"], "safety")
add("https://techcrunch.com/2026/08/11/googles-gemini-app-surges-to-one-billion-users/",
    "Google Says Gemini App Hits One Billion Users",
    "Google reported the Gemini app reached a billion users, a scale figure that says little about depth of engagement.",
    ["models","apps"], "models")
add("https://www.bloomberg.com/news/articles/2026-08-12/ai-coding-startup-lovable-raises-400-million-at-13-3-billion-valuation",
    "Lovable Raises 400 Million Dollars at 13.3 Billion Valuation",
    "The AI coding startup Lovable closed a 400 million dollar round at a 13.3 billion valuation.",
    ["funding","code"], "funding")
add("https://www.bloomberg.com/news/newsletters/2026-08-12/ai-is-creating-a-new-path-for-musical-stardom-with-uncertain-staying-power",
    "AI Opens a New Path to Musical Stardom",
    "AI-made music is producing viral acts, though whether any of it holds an audience remains unclear.",
    ["art","multimodal"], "models")
add("https://professional.bloomberg.com/products/bloomberg-terminal/ai/",
    "AI on the Bloomberg Terminal",
    "A product page describing AI features built into the Bloomberg Terminal.",
    ["enterprise"], "funding")
add("https://www.theguardian.com/technology/2026/aug/12/ai-job-destruction",
    "AI Was Supposed to Destroy Jobs. Where Is the Carnage",
    "A look at why predicted AI job losses have not shown up clearly in employment data so far.",
    ["policy","enterprise"], "funding")
add("https://www.bloomberg.com/news/articles/2026-08-12/andreessen-horowitz-tiger-global-back-yuno-s-45-million-round",
    "a16z and Tiger Global Back Yuno's 45 Million Dollar Round",
    "Payments infrastructure firm Yuno raised 45 million dollars from Andreessen Horowitz and Tiger Global.",
    ["funding"], "funding")
add("https://links.message.bloomberg.com/s/c/Zo5QVVBvgoz7fjfNV3FfTsvTeduWYQE7dYwYkpd9GfgHg604vcsg4IBkVo0gbX_iSZzWontdV28p3XWmppe5YggbZ1Fy0TKWYF8ygJmcTM_b-c4IIl-meky9DZ4rgGQrFVxqfjd1VD_0slH_NuCWKQg92TFplYkVQYJqHjgHWPWWAPSYsfZvaJlpfV62S66An2f9jiCKqoMEliboVDPZ1PGrEGwVLm87KJkJwwnyUaIK8OQZmJ5Sqpvl0Dq4-4-zDDw2LfDnaI3DrojMDAroCAbfkTIlXK-cPuQGdeYdvWlcEgTFWSZfWLefgcTEbcqBC-sTZmKDn8neXX5cW6MKhCV-LiSPWeMj4VWbPYUQ9R0lZg5DYXKO3cjRHvs/DrNv-ZA52_M-AamEJfIvlYhzQ8t-aQhd/11",
    "Apollo Research",
    "A pointer to work from Apollo Research, which focuses on evaluating deceptive behavior in frontier models.",
    ["safety","alignment"], "safety")
add("https://www.bloomberg.com/news/articles/2026-08-11/coreweave-revenue-surges-on-booming-demand-for-ai-computing",
    "CoreWeave Shares Jump on AI Compute Demand",
    "CoreWeave beat expectations and raised its outlook on continued demand for AI computing capacity.",
    ["funding","hardware"], "funding")
add("https://openai.com/index/how-enterprises-put-ai-to-work",
    "How Enterprises Put AI to Work",
    "An OpenAI writeup arguing enterprises are moving from AI assistance toward AI executing tasks.",
    ["enterprise","agents"], "tools")
add("https://www.ft.com/content/33094bff-546e-4ac2-a949-af2e9daaa3f0?syn-25a6b1a6=1",
    "Humans Cannot Remain Passengers in the AGI Car",
    "An opinion piece arguing people must stay actively involved in steering AGI development rather than deferring to it.",
    ["agi","policy"], "safety")

# batch 2
add("https://www.theguardian.com/commentisfree/2026/aug/12/openai-anthropic-ai-models",
    "The Case for Nationalizing OpenAI and Anthropic",
    "Bruce Schneier and Nathan Sanders argue that if markets falter, the US should take frontier labs into public ownership.",
    ["policy"], "safety")
add("https://www.ft.com/content/725b4d15-bd8d-4083-a04e-db016338af2e?syn-25a6b1a6=1",
    "Vance Asked Ukraine to Halt Strikes on Tankers at Russian Port",
    "A geopolitical report on US pressure over Ukrainian strikes affecting a Russian oil port.",
    ["policy"], "funding")
add("https://www.bloomberg.com/news/articles/2026-08-12/jumia-wins-ifc-axian-backing-in-50-million-equity-fundraising",
    "Jumia Wins IFC and Axian Backing in 50 Million Dollar Raise",
    "African e-commerce firm Jumia raised 50 million dollars in equity from IFC and Axian.",
    ["funding"], "funding")
add("https://huggingface.co/blog/LiquidAI/lfm2-5-vl-3b",
    "Liquid AI Releases LFM2.5-VL-3B Vision Model",
    "Liquid AI published LFM2.5-VL-3B, a small vision-language model aimed at faster on-device inference.",
    ["models","multimodal","opensource"], "opensource")
add("https://www.bloomberg.com/news/articles/2026-08-12/lightspeed-seeks-600-million-for-anthropic-openai-wagers",
    "Lightspeed Seeks 600 Million Dollars for AI Bets",
    "Lightspeed is raising a 600 million dollar vehicle to back positions in Anthropic and OpenAI.",
    ["funding"], "funding")
add("https://www.bloomberg.com/news/articles/2026-08-12/mark-bezos-fund-faces-fight-to-recoup-losses-from-fence-startup",
    "Mark Bezos Fund Fights to Recoup Startup Losses",
    "A fund tied to Mark Bezos is in a dispute to recover losses from a failed fence startup.",
    ["funding"], "funding")
add("https://www.theguardian.com/technology/2026/aug/10/meta-child-safety-google-executives-ai-techscape",
    "Meta Faces Costly Child Safety Reckoning",
    "Scrutiny mounts over Meta's handling of child safety as regulators and litigation press the company.",
    ["safety","policy"], "safety")
add("https://www.bloomberg.com/news/articles/2026-08-12/nebius-reports-514-jump-in-ai-cloud-sales-as-demand-booms",
    "Nebius Reports 514 Percent Jump in AI Cloud Sales",
    "Nebius posted a 514 percent increase in AI cloud revenue on strong compute demand.",
    ["funding","hardware"], "funding")
add("https://www.bloomberg.com/news/articles/2026-08-12/new-york-city-probes-prediction-markets-over-ads-social-harms",
    "New York City Probes Kalshi and Polymarket",
    "NYC opened an inquiry into prediction markets Kalshi and Polymarket over advertising and social harms.",
    ["policy"], "funding")
add("https://www.bloomberg.com/news/articles/2026-08-12/nvidia-partner-hon-hai-s-profit-beats-on-sustained-ai-spending",
    "Hon Hai Profit Beats on Sustained AI Spending",
    "Nvidia partner Hon Hai reported a profit beat driven by ongoing AI hardware demand.",
    ["funding","hardware"], "funding")
add("https://www.bloomberg.com/news/articles/2026-08-12/nvidia-backed-startup-coderabbit-valued-at-1-5-billion-in-round",
    "CodeRabbit Valued at 1.5 Billion Dollars",
    "The Nvidia-backed code review startup CodeRabbit reached a 1.5 billion dollar valuation in a new round.",
    ["funding","code"], "funding")
add("https://www.ft.com/content/13ca1246-faa7-4a0e-8117-439aee14d3d7?syn-25a6b1a6=1",
    "Revolut Cuts WeWork Access for Premium Customers",
    "Revolut trimmed a WeWork perk for premium users after price increases.",
    ["enterprise"], "funding")
add("https://www.ft.com/content/107b354b-ba03-44f2-9939-517cbcc11cd0?syn-25a6b1a6=1",
    "Eskom Targets Data Center Demand for Power Surplus",
    "South Africa's Eskom wants to sell surplus power to a growing data center market.",
    ["funding","hardware"], "funding")
add("https://www.theguardian.com/technology/2026/aug/11/spotify-label-ai-artists-block-them-from-some-playlists",
    "Spotify to Label AI Artists and Limit Recommendations",
    "Spotify will mark AI-generated artists and stop recommending them in some playlists.",
    ["art","policy"], "safety")
add("https://www.bloomberg.com/news/articles/2026-08-11/super-micro-gives-sales-forecast-that-tops-rosiest-projections",
    "Super Micro Guidance Tops Projections",
    "Super Micro issued a sales forecast above the most optimistic estimates on AI server demand.",
    ["funding","hardware"], "funding")
add("https://www.ft.com/content/7d2ab3e0-9085-48f6-b38a-d90260d58795?syn-25a6b1a6=1",
    "Taiwan Nuclear Agency Hit by Autonomous AI Hack",
    "Taiwan's nuclear agency was breached in an attack described as autonomous and linked to China.",
    ["safety"], "safety")
add("https://www.bloomberg.com/news/videos/2026-08-12/tech-investments-boost-norway-s-sovereign-wealth-fund-video",
    "Tech Bets Lift Norway's Sovereign Wealth Fund",
    "Norway's wealth fund credited technology holdings for stronger returns.",
    ["funding"], "funding")
add("https://www.bbc.co.uk/sounds/play/w3ct8jy8?at_medium=RSS&at_campaign=rss",
    "Tech Life",
    "The BBC technology podcast covering recent developments across the sector.",
    ["apps"], "tools")
add("https://www.bloomberg.com/news/articles/2026-08-12/tencent-sales-top-estimates-on-wechat-ad-surge-resilient-games",
    "Tencent Sales Top Estimates as AI Spending Rises",
    "Tencent beat revenue estimates on WeChat ad growth and said it is accelerating AI investment.",
    ["funding","enterprise"], "funding")
add("https://www.bloomberg.com/news/newsletters/2026-08-12/tencent-s-ai-innovation-pace-in-question-after-earnings",
    "Questions Over Tencent's AI Innovation Pace",
    "Analysts questioned whether Tencent's AI product cadence keeps up with peers after earnings.",
    ["models","enterprise"], "models")
add("https://www.theguardian.com/commentisfree/2026/aug/11/the-guardian-view-on-ai-money-in-us-politics-not-the-way-to-hold-an-urgent-democratic-debate",
    "AI Money in US Politics",
    "An editorial warning that industry money is distorting the debate over how to govern AI.",
    ["policy"], "safety")
add("https://huggingface.co/blog/ibm-research/altk-evolve-sldd",
    "Doing ACE-Style Context Engineering With Fewer Tokens",
    "IBM Research describes a method to get adaptive context engineering benefits at lower token cost.",
    ["inference","agents"], "tools")
add("https://www.bbc.co.uk/news/articles/c872r52x7jgo?at_medium=RSS&at_campaign=rss",
    "Why Making AI Pay Is Tricky",
    "A look at the difficulty of building durable business models around AI products.",
    ["funding","enterprise"], "funding")
add("https://www.ft.com/content/a87d7d98-92b8-48cc-8b8d-868bb1f79034?syn-25a6b1a6=1",
    "UK Letting Agents Strained by AI-Assisted Complaints",
    "UK letting agents report a rise in tenant complaints drafted with AI help.",
    ["apps","enterprise"], "models")
add("https://www.bloomberg.com/news/articles/2026-08-12/us-stock-futures-today-borr-cava-coreweave-erock-super-micro",
    "US Stock Futures: CoreWeave, Super Micro in Focus",
    "A markets roundup noting AI-linked names including CoreWeave and Super Micro.",
    ["funding"], "funding")

# batch 3
add("https://www.bloomberg.com/news/articles/2026-08-12/weride-tops-estimates-on-surging-domestic-ride-hailing-demand",
    "WeRide Tops Estimates on Robotaxi Demand",
    "Autonomous driving firm WeRide beat estimates on rising domestic ride-hailing volume.",
    ["funding","robotics"], "funding")
add("https://www.ft.com/content/b93d8030-203b-4445-b4a7-49e52d9b17a5",
    "Who Audits Anthropic",
    "A look at Anthropic's auditor and why the choice matters for scrutiny of the company's finances.",
    ["safety","policy"], "safety")
add("https://www.bloomberg.com/news/articles/2026-08-12/whoop-plans-to-double-size-of-boston-headquarters-ahead-of-ipo",
    "Whoop to Double Boston Headquarters Ahead of IPO",
    "Fitness wearable maker Whoop plans to expand its Boston headquarters as it heads toward an IPO.",
    ["funding"], "funding")
add("https://www.ft.com/content/5224b14f-465c-43a9-8f95-1ec9bb559264?syn-25a6b1a6=1",
    "Why Gamers Embrace Friendslop",
    "A cultural read on why players enjoy rough, AI-flavored social game content.",
    ["apps","art"], "models")
add("https://www.bloomberg.com/news/articles/2026-08-12/wintermute-plans-1-billion-ai-investment-to-compete-on-wall-street",
    "Wintermute Plans 1 Billion Dollar AI Investment",
    "Crypto trading firm Wintermute plans a 1 billion dollar AI push to compete with Wall Street.",
    ["funding"], "funding")
add("https://www.bloomberg.com/news/videos/2026-08-12/yardeni-has-a-case-of-femo-video",
    "Yardeni on Fear of Missing Out in AI Markets",
    "Ed Yardeni discusses investor fear of missing out driving AI-linked equities.",
    ["funding"], "funding")
add("https://www.theguardian.com/film/2026/aug/12/ai-boyfriend-dating-chinese-women-replica-miff-documentary",
    "Chinese Women Choosing AI Boyfriends",
    "A documentary follows women in China who prefer AI companions to human partners.",
    ["apps"], "models")
add("https://www.wired.com/story/new-camera-tricks-on-google-latest-pixel-11-smartphones/",
    "New Camera Tricks on Google's Pixel 11",
    "A rundown of the AI-driven camera features on Google's Pixel 11 phones.",
    ["multimodal","apps"], "tools")
add("https://arstechnica.com/gadgets/2026/08/a-google-insider-spills-the-tea-on-how-the-company-forsook-its-founding-ideals/",
    "A Google Insider on the Company's Drift",
    "An insider account of how Google moved away from its founding principles.",
    ["enterprise"], "funding")
add("https://thehackernews.com/2026/08/a-malicious-sim-card-can-run-attacker.html",
    "Malicious SIM Card Can Run Code in IoT Modems",
    "Researchers show a rigged SIM card can execute attacker code inside cellular IoT modems.",
    ["safety"], "safety")
add("https://techcrunch.com/2026/08/11/accel-closes-oversubscribed-550m-india-fund-within-weeks-19-months-after-its-last/",
    "Accel Closes 550 Million Dollar India Fund",
    "Accel closed an oversubscribed 550 million dollar India fund within weeks of launching it.",
    ["funding"], "funding")
# research
add("https://arxiv.org/abs/2608.07621",
    "CMU-Drive and V2V-VLA for Cooperative Driving",
    "A cooperative multi-agent driving benchmark and vehicle-to-vehicle vision-language-action models with a reasoning evaluation.",
    ["robotics","agents"], "research")
add("https://arxiv.org/abs/2608.07346",
    "A2E: An End-to-End Agent Auditing Engine",
    "A framework for auditing autonomous agents end to end, aimed at catching failures before deployment.",
    ["agents","evals"], "research")
add("https://arxiv.org/abs/2608.10599",
    "Beta-VAEs as Effective Theories",
    "Treats beta-VAEs as effective theories with a tolerance-dependent notion of effective dimension.",
    ["interpretability","training"], "research")
add("https://arxiv.org/abs/2608.08173",
    "DisMorph: Disentangling Distortion From Biological Change",
    "A method to separate technical imaging distortions from genuine biological variation.",
    ["science","interpretability"], "research")
add("https://arxiv.org/abs/2608.08814",
    "360CityArena: Urban Navigation Benchmark for Embodied Agents",
    "A realistic virtual city benchmark for testing embodied agent navigation.",
    ["agents","robotics"], "research")
# opensource
add("https://github.com/NousResearch/hermes-agent",
    "NousResearch/hermes-agent",
    "Nous Research's open agent framework, trending on GitHub.",
    ["agents","opensource"], "opensource")
add("https://github.com/openclaw/openclaw",
    "openclaw/openclaw",
    "An open-source project trending on GitHub.",
    ["opensource"], "opensource")
add("https://huggingface.co/moonshotai/Kimi-K3",
    "moonshotai/Kimi-K3",
    "Moonshot AI's Kimi-K3 weights, trending on Hugging Face.",
    ["models","opensource"], "opensource")
add("https://github.com/affaan-m/ECC",
    "affaan-m/ECC",
    "An open-source project trending on GitHub.",
    ["opensource"], "opensource")
add("https://huggingface.co/MiniMaxAI/MiniMax-H3",
    "MiniMaxAI/MiniMax-H3",
    "MiniMax's MiniMax-H3 model release on Hugging Face.",
    ["models","opensource"], "opensource")
add("https://github.com/huggingface/transformers",
    "huggingface/transformers",
    "The Transformers library, trending again on GitHub.",
    ["opensource","code"], "opensource")

# social tier: themes=[], section discourse
for it in items:
    if it["tier"] == "social":
        O[it["url"]] = {"title": it["title"], "summary": it.get("summary","")[:200], "themes": [], "section": "discourse"}

# coverage check
missing = [u for u in urls if u not in O]
assert not missing, f"MISSING {len(missing)}: {missing}"
extra = [u for u in O if u not in urlset]
assert not extra, f"EXTRA: {extra}"

# write head
json.dump(head, open(os.path.join(run_dir, "curation_head.json"), "w"), indent=1)

# write batches in input order, <=25 each
ordered = [(u, O[u]) for u in urls]
batch, n = [], 0
def flush(batch, n):
    frag = {u: v for u, v in batch}
    fn = os.path.join(run_dir, f"curation_items_{n:02d}.json")
    json.dump(frag, open(fn, "w"), indent=1)
    return fn

files = []
for i in range(0, len(ordered), 25):
    n += 1
    files.append(flush(ordered[i:i+25], n))

print("run_dir", run_dir)
print("total items covered", len(O))
print("files", files)
for f in files:
    print(" ", os.path.basename(f), len(json.load(open(f))))
