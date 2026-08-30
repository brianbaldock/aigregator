#!/usr/bin/env python3
import json, os, sys, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_dir import run_dir_default

rd = run_dir_default()
items = json.load(open(os.path.join(rd, "digest_items.json")))
url = {i: items[i]["url"] for i in range(len(items))}

# TLDR: 6 news-tier picks
tldr_idx = [1, 15, 16, 20, 0, 17]
tldr_order = [url[i] for i in tldr_idx]
tldr_blurbs = {
    url[1]: "Sony Music Publishing and Warner Chappell sue Anthropic in the Northern District of California, seeking up to $150,000 per work for lyrics used in training.",
    url[15]: "Trump signs an executive order aimed at blocking states from writing their own AI rules, arguing a patchwork would stifle the industry.",
    url[16]: "The WSJ argues Big Tech's real AI outlay is about $3 trillion larger than balance sheets show, because data-center leases and chip commitments sit off the books.",
    url[20]: "Tencent releases Hy4 Preview, a 770B-parameter (49B active) open weights text model with a 1M-token context window, up sharply from its prior release.",
    url[0]: "South Korea's 'AI for All' program offers every citizen free, unlimited access to homegrown chatbots to cut reliance on US and Chinese models.",
    url[17]: "Zuckerberg outlines Meta's AI ambitions and warns against concentrating advanced AI, releasing a new model with open-source access for developers.",
}

subtitle = ("Washington moves to preempt state AI rules as Trump signs an order and House "
            "Republicans add a ban, while Sanders and AOC push a data-center moratorium. "
            "Sony and Warner Chappell sue Anthropic, and Tencent ships the 770B Hy4 open weights model.")

# Per-index overlay: (title, summary, themes, section)
O = {}
O[0] = ("South Korea's 'AI for All' Push Gives Free Access to Every Citizen",
        "Seoul will fund unlimited access to homegrown chatbots to steer citizens away from US and Chinese models.",
        ["policy", "apps"], "safety")
O[1] = ("Sony Music Publishing and Warner Chappell Are Suing Anthropic",
        "The two publishers filed suit in the Northern District of California over tens of thousands of copyrighted lyrics, seeking up to $150,000 per work.",
        ["policy", "art"], "safety")
O[2] = ("Aliko Dangote's Daughters Join Succession Plan",
        "Ahead of Africa's largest IPO, Dangote brings his three daughters into the group's succession plan.",
        ["funding"], "funding")
O[4] = ("Grindr Bets Wealthy Gay Men Will Pay More to Find the Right Match",
        "Grindr's CEO plans a premium matchmaking tier to boost growth.",
        ["apps"], "funding")
O[5] = ("Gamescom 2026: What Stood Out This Year",
        "A BBC reporter's walkthrough of the biggest games shown in Cologne.",
        ["video"], "projects")
O[6] = ("Meta's Settlement Is a Starting Point",
        "An FT column argues governments can use Meta's settlement as a bargaining chip while weighing social media bans for minors.",
        ["policy"], "safety")
O[7] = ("Nepal Races to Find Missing Amid Threats of Further Flooding",
        "Rescue crews search for thousands missing five days after a glacial collapse triggered flooding on the China border.",
        ["policy"], "safety")
O[8] = ("PetroChina First-Half Profit Rises 22% on Higher Oil Prices",
        "PetroChina posted a 22% jump in first-half profit as energy prices lifted upstream revenue.",
        ["funding"], "funding")
O[9] = ("The Datacenter Fight Could Permanently Transform US Politics",
        "The Guardian tracks how local opposition to AI data centers is realigning voters across party lines.",
        ["funding", "policy"], "funding")
O[10] = ("Women in UK Arts Feel They Lack Equal Opportunities, Report Says",
         "A report finds most women in the arts experience unconscious bias or sexism, especially as they age.",
         ["bias"], "safety")
O[11] = ("House Republicans Include a 10-Year Ban on States Regulating AI",
         "A clause in the Republican tax bill would bar states and localities from regulating AI for a decade.",
         ["policy"], "safety")
O[12] = ("New Group Aims to Help People Adapt to AI Job Losses",
         "RAISE US, a bipartisan nonprofit, launches with more than $500 million for state education and training programs.",
         ["policy"], "safety")
O[13] = ("Progressives Push Bill Imposing AI Data Center Moratorium",
         "Sanders and AOC back a moratorium meant to give lawmakers time to weigh AI and data-center risks.",
         ["policy", "funding"], "safety")
O[14] = ("Top Developers Are Pivoting From Chatbots to Physical AI",
         "Researchers frame 'world models' as the next step past the language models behind chatbots.",
         ["models", "robotics"], "models")
O[15] = ("Trump Signs Order to Block State AI Regulations",
         "The executive order aims to stop states from enacting their own AI rules, citing risk to the industry.",
         ["policy"], "safety")
O[16] = ("Why Big Tech's AI Spending Is $3 Trillion Higher Than It Seems",
         "Data-center leases and chip commitments kept off balance sheets understate the true scale of AI spending.",
         ["funding", "hardware"], "funding")
O[17] = ("Zuckerberg Outlines Meta's Ambitions for AI",
         "Meta ships a new developer model with open-source access as Zuckerberg warns against concentrating advanced AI.",
         ["models", "opensource"], "models")
O[18] = ("Five Critical WordPress Plugin and Theme Flaws Enable Site Takeover",
         "Disclosed flaws in WPMU DEV, Avada, TranslatePress, Pods, and GiveWP allow auth bypass and code execution.",
         ["safety"], "safety")
O[19] = ("Inside Meta's Push to Put Robots to Work in Data Centers",
         "Meta is testing robots on tasks currently handled by data-center technicians.",
         ["robotics"], "projects")
O[20] = ("Tencent Introduces Hy4 Preview",
         "A 770B-parameter open weights model (49B active) with a 1M-token context window, a large step up from Tencent's prior release.",
         ["models", "opensource"], "models")
O[21] = ("METR and Redwood Post a Postmortem of the HuggingFace Hack",
         "The writeup dissects the HuggingFace incident and the alignment and infrastructure steps taken in response.",
         ["safety", "alignment"], "safety")
O[22] = ("Nvidia's AI Advantage Is Moving Beyond the GPU",
         "The next generation of data-center systems leans on smarter traffic control rather than raw processor cycles.",
         ["hardware", "inference"], "funding")
O[23] = ("TerminalFix Uses Fake Cloudflare CAPTCHAs to Deploy a Backdoor",
         "Microsoft details a ClickFix variant that tricks users into running malicious commands in Windows Terminal.",
         ["safety"], "safety")
O[24] = ("Why the Hottest New Wearables Want to Be Ignored",
         "A crop of minimalist wearables collects health data without demanding attention.",
         ["hardware", "apps"], "projects")
O[25] = ("Vijay Pande on Betting Small After Running $4 Billion at a16z",
         "Pande explains leaving a16z's biotech practice to start the smaller, AI-native VZVC as biology shifts toward engineering.",
         ["funding", "science"], "funding")
O[26] = ("2026 Global Technology Leadership Study: An AI-First Agenda",
         "Deloitte's CIO study finds technology leaders shifting from operational stewards to enterprise strategists.",
         ["enterprise"], "funding")
O[27] = ("As AI Accelerates, Smartphones Enter a New Wave of Innovation",
         "A Samsung-sponsored piece on how AI, smart rings, and XR reshape the smartphone.",
         ["apps", "hardware"], "projects")
O[28] = ("Putting Agentic AI to Work",
         "An AWS and monday.com piece on measurement, governance, and context gaps facing enterprise agents.",
         ["agents", "enterprise"], "tools")
O[29] = ("Anthropic Builds a New Enterprise AI Services Company With Blackstone",
         "Anthropic partners with Blackstone and Hellman & Friedman to stand up an enterprise AI services company.",
         ["funding", "enterprise"], "funding")
O[30] = ("Anthropic: Developing a Computer Use Model",
         "Claude can follow commands to move a cursor, click, and operate a computer through the right software setup.",
         ["agents", "models"], "tools")
O[31] = ("Funding Better Evaluations of AI's Impact on Wellbeing",
         "Anthropic launches a $5 million grant program for independent research into AI's effect on user wellbeing.",
         ["safety", "evals"], "safety")
O[32] = ("How Claude's Text Watermark Works",
         "Future Claude models will embed a watermark to estimate the likelihood that Claude wrote a given text.",
         ["safety", "interpretability"], "safety")
O[33] = ("Introducing the Model Context Protocol",
         "MCP is an open standard for connecting AI assistants to data repositories, business tools, and dev environments.",
         ["agents", "opensource"], "tools")
O[35] = ("Previewing the Model Hardware Standard",
         "Anthropic opens a research preview of a shared spec for agents to operate physical devices safely.",
         ["robotics", "agents"], "tools")
O[36] = ("Anthropic Raises Series E at $61.5B Post-Money Valuation",
         "Anthropic raised $3.5 billion in a round led by Lightspeed, with Bessemer, Cisco, D1, and Fidelity participating.",
         ["funding"], "funding")
O[37] = ("Open Weights != Open Source",
         "A LessWrong post argues that releasing weights is not the same as releasing open source.",
         ["opensource"], "opensource")
O[38] = ("Open Weights: Not Quite What You've Been Told",
         "The OSI walks through what open weights actually mean versus open-source licensing.",
         ["opensource"], "opensource")
O[39] = ("Open-Source LLM Leaderboard 2026: 106 Models Ranked",
         "Qwen3.8 Max tops the August open-weight ranking at 79.2, with Hy4 Preview close behind.",
         ["opensource", "evals"], "opensource")
O[40] = ("Which Open Source Local LLM to Try for Coding",
         "A LocalLLM thread weighs open-weight options for local coding assistants.",
         ["opensource", "code"], "opensource")
O[41] = ("NousResearch/hermes-agent",
         "An agent framework trending on GitHub at roughly 238k stars with a fresh push.",
         ["opensource", "agents"], "opensource")
O[42] = ("openclaw/openclaw",
         "A cross-platform personal AI assistant trending on GitHub near 388k stars.",
         ["opensource", "agents"], "opensource")
O[43] = ("Qwen/Qwen3.8-27B",
         "An image-text-to-text model trending on HuggingFace with millions of downloads.",
         ["opensource", "multimodal"], "opensource")
O[44] = ("affaan-m/ECC",
         "An agent-harness performance system for Claude Code, Codex, Opencode, and Cursor, trending near 244k stars.",
         ["opensource", "agents", "code"], "opensource")
O[45] = ("MiniMaxAI/MiniMax-H3",
         "An image-text-to-video model trending on HuggingFace with millions of downloads.",
         ["opensource", "video", "multimodal"], "opensource")
O[46] = ("huggingface/transformers",
         "The model-definition framework for text, vision, audio, and multimodal models, trending near 165k stars.",
         ["opensource", "training"], "opensource")
# social tier -> discourse
O[47] = ("1M-Context Qwen3.8-27B on Dual 5090s via an NInfer Fork",
         "A hobbyist forks NInfer to add tensor parallelism and YaRN scaling for a million-token context on two consumer GPUs.",
         [], "discourse")
O[48] = ("ACL Findings or TMLR?",
         "A researcher weighs venue options after weak NeurIPS scores.",
         [], "discourse")
O[49] = ("67-84 t/s DeepSeek Flash v4 on Two GX10s",
         "A user reports sustained throughput running DeepSeek Flash v4 across two GX10 boxes.",
         [], "discourse")
O[50] = ("A Hallucination Class That Passes Fact-Checking",
         "A discussion of fabricated quotation marks around otherwise true claims.",
         [], "discourse")
O[51] = ("An Unintentional Tool",
         "A user shares experience with an AI-driven role-playing app and its potential uses.",
         [], "discourse")
O[52] = ("Anthropic Offers 10,000 Claude Seats to Research Labs",
         "Anthropic opens one-year Claude Team seats to verified academic and nonprofit labs, prompting debate over what the program should require.",
         [], "discourse")
O[53] = ("Benchmarking Pocket-Scale Inference",
         "Artificial Analysis benchmarks LLM inference on mobile phones.",
         [], "discourse")
O[54] = ("Claude Session URL Appended to Commit Messages by Default",
         "A Claude Code issue over session URLs being added to commits and PR descriptions by default.",
         [], "discourse")
O[55] = ("Debian Votes to Allow Responsible Use of Generative AI",
         "Debian passes a resolution permitting responsible generative AI use.",
         [], "discourse")
O[56] = ("Defrag98: A Windows 98 Defragmenter Simulator",
         "An online recreation of the Windows 98 disk defragmenter.",
         [], "discourse")
O[57] = ("Domain-Driven Agents",
         "A post on applying domain-driven design ideas to agent architectures.",
         [], "discourse")
O[58] = ("Fair Work Commission Condemns 'Plain Wrong' AI Legal Advice",
         "An Australian tribunal criticizes AI-generated legal submissions.",
         [], "discourse")
O[59] = ("Good Culture Is the Biggest Productivity Hack, Not AI",
         "A newsletter argues team culture outweighs AI tooling for productivity.",
         [], "discourse")
O[60] = ("LLMs Are Making Me Lose My Savviness",
         "A developer reflects on skill atrophy from leaning on LLMs.",
         [], "discourse")
O[61] = ("Car Insurance Fees Funded Flock Cameras in Texas",
         "A $1 auto-insurance surcharge quietly funded Flock surveillance cameras.",
         [], "discourse")

# Build overlays keyed by real URL, skip hub pages (3, 34)
skip = {3, 34}
overlays = {}
for i in range(len(items)):
    if i in skip:
        continue
    t, s, themes, section = O[i]
    overlays[url[i]] = {"title": t, "summary": s, "themes": themes, "section": section}

# head
head = {"subtitle": subtitle, "tldr_order": tldr_order, "tldr_blurbs": tldr_blurbs}
json.dump(head, open(os.path.join(rd, "curation_head.json"), "w"), ensure_ascii=False, indent=2)

# batches of at most 25
keys = list(overlays.keys())
batches = [keys[i:i+25] for i in range(0, len(keys), 25)]
for n, batch in enumerate(batches, 1):
    frag = {k: overlays[k] for k in batch}
    json.dump(frag, open(os.path.join(rd, f"curation_items_{n:02d}.json"), "w"), ensure_ascii=False, indent=2)

print("wrote head +", len(batches), "batches,", len(overlays), "overlays into", rd)
