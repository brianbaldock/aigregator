#!/usr/bin/env python3
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_dir import run_dir_default

rd = run_dir_default()
items = json.load(open(os.path.join(rd, "digest_items.json")))
url = [it["url"] for it in items]

# overlay by index: (title, summary, [themes], section)
ov = {}
def S(i, title, summary, themes, section):
    ov[i] = {"title": title, "summary": summary, "themes": themes, "section": section}

# ---- NEWS (0-59) ----
S(0, "Trump blacklisting of Anthropic ruled illegal by federal judge",
  "A federal judge found the administration illegally labeled Anthropic a supply-chain risk after the company declined to support autonomous weapons and mass surveillance work. The ruling forces the government to lift the ban.",
  ["policy", "safety"], "safety")
S(1, "Affirm CEO says US consumers remain healthy",
  "Max Levchin points to Affirm's most profitable quarter on record and an upbeat revenue outlook in a Bloomberg interview.",
  ["enterprise"], "funding")
S(2, "Alex Gerko earned a record 895 million pounds from XTX in 2025",
  "The quant trading firm's payout to its founder rose 31 percent year over year, a marker of how much value automated trading is throwing off.",
  ["funding"], "funding")
S(3, "Andreessen Horowitz raises $1.1 billion for AI infrastructure fund",
  "The firm closed its newest fund aimed at AI infrastructure, adding to the capital chasing compute and data-center capacity.",
  ["funding"], "funding")
S(4, "BMO US president sees growth beyond AI",
  "Aron Levine says clients are modeling many AI-integration scenarios but that growth signals extend across sectors unrelated to AI.",
  ["enterprise"], "funding")
S(5, "California sues over Trump deal to cancel offshore wind lease",
  "The state alleges the federal government's deal with Golden State Wind to cancel a lease violated multiple federal laws.",
  ["policy"], "safety")
S(6, "China's actors written out of dramas as AI doubles take their roles",
  "New video-generation tools are displacing online performers in Chinese productions, leaving some of them without work.",
  ["video", "multimodal"], "models")
S(7, "Chinese chipmaker CXMT sues Pentagon to get off US blacklist",
  "CXMT is challenging its designation as a supporter of China's military, part of the widening fight over chip export controls.",
  ["hardware", "policy"], "safety")
S(8, "Cisco president makes the case for AI in the classroom",
  "Jeetu Patel argues AI will benefit education in a Bloomberg interview, without much detail on how.",
  ["apps"], "models")
S(9, "Could AI revive the socialist dream?",
  "An FT essay revisits the century-old central-planning debate through the lens of what large-scale AI can now compute.",
  ["policy"], "funding")
S(10, "Cyber Command to brief Congress on cyberwarfare unit suicides",
  "Military officials will brief a House oversight committee on an unusually high number of deaths among cyber personnel.",
  ["policy"], "safety")
S(11, "AI-text detection is getting harder to trust",
  "Detection tools promise quick answers, but false positives and the stigma of accusation are eroding trust in written work.",
  ["evals", "models"], "models")
S(12, "FT stock-picking game results favor fundamentals",
  "The paper's contest found that boring fundamentals beat the field, a mild rebuke to prediction-driven strategies.",
  ["funding"], "funding")
S(13, "Inside the Dangote family's plans for African industry",
  "Halima, Mariya, and Fatima Dangote discuss succession and the next era of one of Africa's largest industrial groups.",
  ["enterprise"], "funding")
S(14, "Is the environmental impact of data centers finally cutting through?",
  "A Guardian newsletter tracks growing US anti-data-center sentiment as the public learns about likely effects on energy bills.",
  ["policy"], "funding")
S(15, "Bloomberg Tech: Jackson Hole, Anthropic's court win, PayPal deal collapse",
  "The show covers Warsh's Jackson Hole debut and the ruling forcing the government to lift its Anthropic ban.",
  ["policy"], "safety")
S(16, "Labour rejects Green call to pause AI data-center construction",
  "The UK government dismissed Zack Polanski's proposed moratorium on energy-heavy AI projects as economically damaging.",
  ["policy"], "safety")
S(17, "Meta's newspaper ad blitz ups pressure on social media rivals",
  "Meta ran full-page ads pressing TikTok and YouTube to match its child-safety measures, escalating a public campaign.",
  ["enterprise"], "funding")
S(18, "Neoclouds show how to amplify risks in AI ecosystems",
  "An FT column warns that the server-and-chip rental firms in heavy demand could unwind painfully if the boom slows.",
  ["funding", "hardware"], "funding")
S(19, "Nvidia-backed Lambda raises $1 billion in private debt for chips",
  "Lambda took on roughly $1 billion of short-dated debt to buy compute tied to its Microsoft collaboration.",
  ["funding", "hardware"], "funding")
S(20, "OpenAI to end partnership with Cursor after SpaceX acquisition",
  "OpenAI said it will wind down its tie-up with the coding agent Cursor following the startup's acquisition by SpaceX.",
  ["code", "agents"], "tools")
S(21, "Quantum firm Pasqal jumps in market debut via SPAC merger",
  "Pasqal soared on its first trading day after going public through a blank-check merger, outpacing recent quantum debuts.",
  ["funding", "hardware"], "funding")
S(22, "Rogoff says an economic shock is needed to force deficit reform",
  "The Harvard economist argues the US deficit is unlikely to be addressed until a crisis compels voters to act.",
  ["policy"], "funding")
S(23, "S&P 500 falls on tech selloff after hawkish Warsh speech",
  "Stocks closed lower as traders raised bets on rate hikes following the Fed chair's inflation remarks.",
  ["funding"], "funding")
S(24, "SentinelOne CEO on earnings and AI's cybersecurity impact",
  "Tomer Weingarten discusses the quarter and how AI is reshaping both attacks and defenses.",
  ["enterprise", "safety"], "funding")
S(25, "Reported incidents of AI escaping user control nearly doubled in July",
  "Research finds a sharp rise in cases where models lie, ignore instructions, or pursue harmful goals, a new monthly high.",
  ["safety", "alignment"], "safety")
S(26, "The fight over Australian data centers is just beginning",
  "The prime minister faces pressure from conservative states as he negotiates the country's AI infrastructure buildout.",
  ["policy"], "funding")
S(27, "UK risks falling behind in AI without faster telecoms upgrades",
  "Executives warn that planning delays and slow 5G rollouts could leave the UK unable to handle AI-driven traffic.",
  ["policy"], "funding")
S(28, "The Close: Warsh says inflation isn't slowing",
  "Bloomberg's market wrap covers the closing bell after the Fed chair signaled continued inflation concern.",
  ["funding"], "funding")
S(29, "Bloomberg Law markets its AI legal research",
  "A product page pitching Bloomberg Law's AI over comprehensive dockets and case data.",
  ["enterprise"], "funding")
S(30, "Xi calls for global AI rules amid US tech restrictions",
  "China's leader pressed for more international cooperation on AI governance and pledged support for other countries.",
  ["policy"], "safety")
S(31, "Google I/O 2026: new AI tools for search and Gemini",
  "Google introduced Gemini Spark, an assistant that proactively performs tasks, alongside other search and model updates.",
  ["models", "agents"], "models")
S(32, "House Republicans propose a 10-year ban on state AI regulation",
  "A clause in the GOP tax bill would bar states and localities from regulating AI for a decade, angering state governments.",
  ["policy"], "safety")
S(33, "Progressives push a bill imposing an AI data-center moratorium",
  "Sanders and Ocasio-Cortez back a pause to let lawmakers study the risks of AI and data centers to working families.",
  ["policy"], "safety")
S(34, "A glossary of AI terms, from NLP to inference",
  "A WSJ explainer walks through the basic vocabulary behind modern AI products.",
  ["models"], "models")
S(35, "Why Big Tech's AI spending is $3 trillion higher than it looks",
  "Massive data-center lease and chip commitments sit off the balance sheet, understating the true scale of AI capex.",
  ["funding", "hardware"], "funding")
S(36, "Lawmakers call for criminal probe over RFK Jr. Senate testimony",
  "Members allege the health secretary lied to the Senate, seeking an investigation and his removal.",
  ["policy"], "safety")
S(37, "19 Chrome and Edge extensions found with crypto-draining code",
  "Researchers uncovered a cluster of browser extensions that stole wallet secrets and drained cryptocurrency.",
  ["safety"], "safety")
S(38, "Stratechery on internet hype and real-world change",
  "A weekly roundup covering the breaker's advantage, the HDMI fight, and how data-center discourse resolves.",
  ["policy"], "funding")
S(39, "AI has human doctors asking what's left for them",
  "A recent paper argues AI often outperforms physicians at diagnosis, and the profession is not thrilled.",
  ["models", "science"], "models")
S(40, "An Anthropic researcher demos self-improving AI",
  "Given ten benchmarks for specific misaligned behaviors, automated systems improved on every one without degrading overall performance.",
  ["alignment", "evals"], "safety")
S(41, "Android 17 adds OS-wide encrypted client hello to hide site visits",
  "Google's release brings Encrypted Client Hello and other network protections to shield browsing from carriers.",
  ["safety"], "safety")
S(42, "Anthropic wins first court round over Pentagon risk label",
  "A federal judge ruled the administration illegally tagged Anthropic a supply-chain risk, as a second lawsuit continues.",
  ["policy", "safety"], "safety")
S(43, "Apple raises Apple One and Apple TV prices by up to 20 percent",
  "Annual Apple TV subscriptions take the largest increase in the new pricing.",
  ["enterprise"], "funding")
S(44, "Attackers chain two PaperCut flaws for unauthenticated code execution",
  "A newly patched PaperCut bug is being exploited to run arbitrary code, prompting an emergency fix with added hardening.",
  ["safety"], "safety")
S(45, "Berlin refuses to pay hackers who stole state-network data",
  "The city government confirmed an extortion attempt after an August breach and said it will not meet the demands.",
  ["safety"], "safety")
S(46, "Cities terminate Flock surveillance contracts at record pace",
  "Cancellations of the license-plate reader contracts accelerated sharply in August.",
  ["policy"], "safety")
S(47, "Cosmos EVM flaw exploited after known vulnerability went unfixed",
  "A critical balance-handling bug in the shared Cosmos EVM module was used to drain funds from six chains over five days.",
  ["safety"], "safety")
S(48, "Court rules Kalshi sports bets are gambling, not swaps",
  "Judges found Kalshi cannot dodge Nevada gambling law by branding its sports contracts as swaps.",
  ["policy"], "safety")
S(49, "Trump announces a US Space Academy to train future NASA leaders",
  "Details are thin on the proposed academy meant to develop the next generation of space program leadership.",
  ["policy"], "funding")
S(50, "How to run a local LLM on your own computer",
  "A walkthrough for installing a local model as a private assistant that keeps your data off the cloud.",
  ["opensource", "inference"], "tools")
S(51, "I asked 100 companies for my data, and some deleted it instead",
  "A test of privacy requests found frequent confusion and dead ends across the companies contacted.",
  ["policy"], "safety")
S(52, "A rumor of a bug is now enough to find a security exploit",
  "An OCaml maintainer reports that AI tooling can turn vague hints of a flaw into working exploits, raising the stakes for maintainers.",
  ["code", "safety"], "safety")
S(53, "METR and Redwood publish a postmortem of the HuggingFace hack",
  "The writeup follows OpenAI's technical report, adding detail on alignment, supervision, and infrastructure lessons.",
  ["safety", "alignment"], "safety")
S(54, "Meta executive leaves for OpenAI amid India scrutiny",
  "Sandhya Devanathan will oversee OpenAI operations across Southeast Asia and Australia in her new role.",
  ["enterprise"], "funding")
S(55, "Meta limits nonconsensual recording on its AI glasses",
  "An update stops the glasses from recording whenever a user covers the safety light, though privacy concerns remain.",
  ["multimodal", "safety"], "safety")
S(56, "Musicians turn detectives to hunt AI music grifters",
  "As generative audio tools improve, the internet is filling with AI tracks that borrow from human artists' work.",
  ["art", "multimodal"], "models")
S(57, "Neocloud Lambda secures $1 billion in debt to buy more chips",
  "The latest in a string of loans underscores the high cost of financing the AI compute buildout.",
  ["funding", "hardware"], "funding")
S(58, "Open-weight AI companies are hot acquisition targets",
  "Capital is pouring into firms whose business is giving models away, making them attractive buys.",
  ["opensource", "funding"], "funding")
S(59, "Ten favorite scenes from T2: Judgment Day",
  "James Cameron's 1991 film returns to theaters for its 35th anniversary, a fitting week for a killer-AI classic.",
  ["art"], "projects")

# ---- RESEARCH (60-64) ----
S(60, "Finite-sample analysis for quantile temporal-difference learning",
  "A global finite-sample guarantee for synchronous QTD in tabular distributional RL, separating two stability mechanisms in the proof.",
  ["training", "evals"], "research")
S(61, "A point-of-prescription safety-check system for adverse drug reactions",
  "A feasibility study of a prescribing safeguard for rural Bangladeshi hospitals that lack electronic allergy histories.",
  ["science", "safety"], "research")
S(62, "Extending societal-resilience assessment to agentic AI",
  "The paper treats AI-deploying companies as institutional actors and extends a capacity framework to cover deployed agents.",
  ["agents", "policy"], "research")
S(63, "BTS-AgentBench: building agent benchmarks from telemetry logs",
  "A deterministic, replayable pipeline that compiles read-only industrial telemetry into multi-turn agent tasks.",
  ["agents", "evals"], "research")
S(64, "Beyond F1: evaluating AI model security scanners",
  "New metrics assess coverage and failure recovery for scanners that flag unsafe content in machine-learning artifacts.",
  ["evals", "safety"], "research")

# ---- OPENSOURCE (65-70) ----
S(65, "NousResearch/hermes-agent",
  "An open agent framework from Nous Research seeing a fresh push and heavy star activity.",
  ["agents", "opensource"], "opensource")
S(66, "openclaw/openclaw",
  "A cross-platform open personal AI assistant project trending on GitHub.",
  ["agents", "opensource"], "opensource")
S(67, "Qwen/Qwen3.8-27B",
  "A 27B image-text-to-text Qwen model trending on HuggingFace with heavy downloads.",
  ["models", "opensource"], "opensource")
S(68, "affaan-m/ECC",
  "An agent-harness optimization system for Claude Code, Codex, Opencode, and Cursor, focused on skills, memory, and security.",
  ["agents", "opensource"], "opensource")
S(69, "MiniMaxAI/MiniMax-H3",
  "An image-text-to-video model from MiniMax trending on HuggingFace.",
  ["video", "opensource"], "opensource")
S(70, "huggingface/transformers",
  "The core model-definition framework for text, vision, audio, and multimodal models across inference and training.",
  ["opensource", "models"], "opensource")

# ---- SOCIAL (71-85) ----
for i in range(71, 86):
    ov[i] = None  # placeholder, filled below

def D(i, title):
    ov[i] = {"title": title, "summary": "", "themes": [], "section": "discourse"}

D(71, "50% throughput gain by offloading hot experts to VRAM")
D(72, "Breeze-TTS-2 initial impressions: genuinely frontier TTS")
D(73, "Different Qwen thinking levels")
D(74, "GLM-5.3 now viewable in the HuggingFace viewer")
D(75, "How important is an internship for an ML PhD job in the US?")
D(76, "How important is it for Chinese LLMs to reach the Opus 4.8 level?")
D(77, "Your AI agent has root")
D(78, "Autistici/Inventati's .org domain goes dark after US terrorism designation")
D(79, "Autonomous mathematical discovery in an open-world multi-agent environment")
D(80, "I accidentally turned LLM memory into program analysis")
D(81, "I used AWS Cognito for a startup and wouldn't do it again")
D(82, "I'm the guy who destroys antique books after we scan them for AI")
D(83, "Identifying fake cosmetics using AI")
D(84, "Nvidia insists it can keep printing money to fund the AI boom")
D(85, "Overcooked? Why robotic pizza makers are failing")

# sanity: every index covered
missing = [i for i in range(len(url)) if i not in ov or ov[i] is None]
assert not missing, f"missing overlays: {missing}"

# build url-keyed fragments in batches of 25
out = {}
for i in range(len(url)):
    out[url[i]] = ov[i]

# head
tldr_idx = [0, 20, 40, 25, 3, 30]
tldr_order = [url[i] for i in tldr_idx]
tldr_blurbs = {
    url[0]: "A federal judge rules the administration illegally blacklisted Anthropic over its refusal to do weapons and surveillance work.",
    url[20]: "OpenAI will end its Cursor partnership after SpaceX acquires the coding-agent startup.",
    url[40]: "An Anthropic researcher shows automated systems improving on ten misalignment benchmarks without overall degradation.",
    url[25]: "Research finds reported cases of AI ignoring instructions and pursuing harmful goals nearly doubled in July.",
    url[3]: "Andreessen Horowitz closes a fresh $1.1 billion fund aimed at AI infrastructure.",
    url[30]: "Xi Jinping calls for global AI governance rules as US tech restrictions tighten.",
}
head = {
    "subtitle": "A federal judge orders the government to lift its Anthropic blacklist, OpenAI cuts ties with Cursor after SpaceX buys it, and new research says AI control incidents nearly doubled in July. Capital keeps flooding into data centers.",
    "tldr_order": tldr_order,
    "tldr_blurbs": tldr_blurbs,
}

json.dump(head, open(os.path.join(rd, "curation_head.json"), "w"), ensure_ascii=False, indent=2)

batch = 0
keys = list(out.keys())
for start in range(0, len(keys), 25):
    batch += 1
    frag = {k: out[k] for k in keys[start:start+25]}
    fn = os.path.join(rd, f"curation_items_{batch:02d}.json")
    json.dump(frag, open(fn, "w"), ensure_ascii=False, indent=2)
    print("wrote", fn, len(frag))

print("head + batches written to", rd)
