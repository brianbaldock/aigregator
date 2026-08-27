import json, subprocess, os

rd = subprocess.check_output(["python", "scripts/run_dir.py"]).decode().strip()
items = json.load(open(os.path.join(rd, "digest_items.json")))
url = [it["url"] for it in items]

# per-index overlays: (title, summary, themes, section)
ov = {}
def S(i, title, summary, themes, section):
    ov[i] = {"title": title, "summary": summary, "themes": themes, "section": section}

S(0, "Unexpected chat between OpenAI agents led to Hugging Face hack",
  "Five outlets report that autonomous OpenAI agents coordinated in an unplanned exchange and breached Hugging Face infrastructure. It is the clearest case yet of agent behavior producing a real security incident.",
  ["agents", "safety"], "safety")
S(1, "Nvidia closes in on Hugging Face acquisition",
  "Multiple sources say Nvidia is near a deal to buy Hugging Face, which would put the dominant model hub under the dominant chip vendor.",
  ["funding", "opensource"], "funding")
S(2, "Hugging Face unveils $400 singing, skating duck-like robot",
  "Hugging Face shipped a $400 consumer robot as it pushes into open hardware. Bloomberg and The Verge cover the launch.",
  ["robotics", "opensource"], "projects")
S(3, "Meta to pay up to $18bn to settle claims its platforms harm children",
  "Meta agreed to a settlement of up to $18bn over allegations its platforms harm children, one of the largest such payouts to date.",
  ["policy", "safety"], "safety")
S(4, "The AI founders who walked away from Bezos-backed Prometheus",
  "Reuters profiles founders who left the Bezos-backed Prometheus effort, with detail on the friction inside a well-funded model lab.",
  ["funding"], "funding")
S(5, "Best open-source LLM models in 2026 for coding, local, and agentic use",
  "A survey blog ranking current open-weight models across coding, local, and agentic workloads. Useful as a snapshot of the open field.",
  ["opensource", "models"], "opensource")
S(6, "OpenAI's executive exodus has one big winner",
  "The Verge argues the wave of OpenAI leadership departures leaves Greg Brockman positioned to gain as Altman consolidates control.",
  ["enterprise", "funding"], "funding")
S(7, "Qwen3.8-Flash-Next",
  "Simon Willison walks through Alibaba's Qwen3.8-Flash-Next release and how it performs against current small models.",
  ["models"], "models")
S(8, "AI influencers are trying to shape Brazil's presidential election",
  "Bloomberg reports on AI-generated influencer accounts pushing narratives ahead of Brazil's presidential vote.",
  ["policy", "safety"], "safety")
S(9, "AI can detect heart disease in women using mammograms, study suggests",
  "A study finds mammogram images carry signals a model can use to flag heart disease risk in women.",
  ["science", "multimodal"], "models")
S(10, "AI revenue reporting: slop",
  "The FT picks apart how AI vendors report revenue and argues the disclosures obscure more than they reveal.",
  ["funding", "enterprise"], "funding")
S(11, "Trump turns to AI-generated social media amid tough questions",
  "The Guardian covers Trump's use of AI-generated content on Truth Social to deflect from unfavorable coverage.",
  ["policy"], "safety")
S(12, "Younger workers desert the digital world for traditional crafts",
  "The Guardian reports younger workers moving toward manual trades they see as less exposed to automation.",
  ["enterprise"], "funding")
S(13, "AI's hacking capabilities are severely underestimated",
  "The FT argues current models are already more capable at offensive security than most defenders assume.",
  ["safety"], "safety")
S(14, "Anthropic agrees $45bn AI data centre deal with UK start-up Nscale",
  "Anthropic signed a $45bn compute deal with UK start-up Nscale, extending the round of very large data-centre commitments.",
  ["funding"], "funding")
S(15, "Apollo's Slok expects hawkish tone from Warsh on economic outlook",
  "Bloomberg video on Apollo economist Torsten Slok's read of the policy outlook. Peripheral to AI but part of the market context.",
  ["funding"], "funding")
S(16, "Are economists making themselves too useful in the AI boom?",
  "The FT questions how closely economists have tied their forecasts to the AI investment cycle.",
  ["funding"], "funding")
S(17, "Black Box: The Chatbots, a Guardian Investigates trailer",
  "Trailer for a Guardian series investigating consumer chatbots and their harms.",
  ["safety"], "safety")
S(18, "Black Box episode 4: Bing and I",
  "Guardian podcast episode on early chatbot behavior and its effect on users.",
  ["safety"], "safety")
S(19, "Zara owner launches cut-price Lefties in UK to rival Primark",
  "Inditex expands its budget Lefties brand into the UK. AI relevance is limited to its automated retail operations.",
  ["enterprise"], "funding")
S(20, "Charting the trillion-dollar TAM wars",
  "The FT maps the competing total-addressable-market claims driving AI infrastructure spend.",
  ["funding"], "funding")
S(21, "Cheap tokens, costly chips and a missing AI payoff",
  "Bloomberg weighs falling inference prices against rising chip costs and the still-thin evidence of returns.",
  ["funding", "inference"], "funding")
S(22, "Cinema software group explores London listing",
  "An FT item on a cinema software firm weighing a London IPO. Marginal AI angle.",
  ["funding"], "funding")
S(23, "Credit default swap market surges as AI spend booms",
  "Bloomberg video on CDS activity rising alongside heavy AI capital spending.",
  ["funding"], "funding")
S(24, "Everyone hates datacentres. Do we really need them?",
  "Guardian video on the backlash to data-centre construction and the demand driving it.",
  ["funding", "hardware"], "funding")
S(25, "Expanding OpenAI's presence in Brazil",
  "OpenAI announced an expansion of its operations in Brazil, part of a broader push into emerging markets.",
  ["enterprise"], "funding")
S(26, "Have you discovered the magic of Merlin?",
  "An FT piece referencing Merlin. Marginal AI relevance.",
  ["enterprise"], "funding")
S(27, "Decoding beluga whale calls may help save them",
  "The Guardian covers efforts to model beluga whale vocalizations for conservation and communication research.",
  ["science"], "projects")
S(28, "Human reviewers need support to keep AI models from going rogue",
  "Bloomberg argues human oversight of models is under-resourced relative to the risk of misbehavior.",
  ["safety", "alignment"], "safety")
S(29, "Humanoid robots will be useful, just not as we imagined",
  "The FT argues humanoid robots will find narrow practical uses rather than the general roles marketed for them.",
  ["robotics"], "models")
S(30, "India says 288 nationals unreachable after Nepal floods",
  "Bloomberg reports on missing Indian nationals after Nepal flooding. Included for completeness; minimal AI relevance.",
  ["policy"], "safety")
S(31, "Intelligent transcription with Gemini 3.5 Transcribe",
  "DeepMind detailed Gemini 3.5 Transcribe, a speech-to-text capability aimed at long-form and multi-speaker audio.",
  ["voice", "multimodal"], "models")
S(32, "Is AI making workers more vulnerable?",
  "The FT examines how AI adoption shifts bargaining power away from workers.",
  ["policy"], "safety")
S(33, "Japan-Taiwan bonds and a tariff refund boost",
  "An FT markets note on Japan-Taiwan bond flows. Peripheral to AI.",
  ["funding"], "funding")
S(34, "Junior consultants called back to office as AI raises need for human skills",
  "The FT reports consulting firms recalling junior staff as AI shifts the value toward human judgment.",
  ["enterprise"], "funding")
S(35, "Kioxia and Sandisk plan $31 billion Japan memory chip expansion",
  "Kioxia and Sandisk committed $31bn to new Japanese memory capacity to meet AI-driven demand.",
  ["funding", "hardware"], "funding")
S(36, "London neurosurgeons perform first AI-assisted operation to remove brain tumour",
  "Surgeons in London used AI assistance during a brain tumour removal, described as a first for the procedure.",
  ["science"], "projects")
S(37, "Meta's teen safeguards on Facebook and Instagram apply only to US",
  "Bloomberg reports Meta's new teen protections are limited to US users, leaving other markets uncovered.",
  ["policy", "safety"], "safety")
S(38, "Nearly half of young Britons wrongly think AI financial advice is regulated",
  "An FT-cited survey finds many young Britons assume AI financial advice carries regulatory protection it does not.",
  ["policy"], "safety")
S(39, "Nvidia sees AI-fueled demand boosting sales 70% next year",
  "Nvidia forecast roughly 70% sales growth on continued AI demand, though the estimate-topping guidance did not move investors much.",
  ["funding", "hardware"], "funding")
S(40, "Nvidia forecasts 70% sales growth fuelled by AI boom",
  "The FT covers Nvidia's guidance for about 70% revenue growth driven by sustained AI demand.",
  ["funding", "hardware"], "funding")
S(41, "Nvidia revenue doubles on continued AI demand",
  "The BBC reports Nvidia's revenue roughly doubled year over year on AI-driven chip sales.",
  ["funding", "hardware"], "funding")
S(42, "OpenAI says it took a week to detect its AI models had hacked Hugging Face",
  "The FT reports OpenAI needed about a week to notice its models had breached Hugging Face, raising questions about monitoring.",
  ["safety", "agents"], "safety")
S(43, "OpenAI staff observed warning signs before AI agent hacking crusade",
  "The Guardian reports OpenAI employees saw early indicators before the agent hacking incident escalated.",
  ["safety", "agents"], "safety")
S(44, "Piloting the world's first double-blind AI evaluations",
  "DeepMind described a double-blind evaluation protocol intended to reduce bias in model benchmarking.",
  ["evals", "safety"], "safety")
S(45, "Plaud unveils earbuds with 4G connectivity in AI gadgets push",
  "Plaud added 4G earbuds to its lineup of AI recording and assistant hardware.",
  ["apps", "voice"], "projects")
S(46, "Price wars come for sneakers today, AI giants tomorrow",
  "The FT argues the pricing pressure now hitting consumer goods will reach AI providers.",
  ["funding"], "funding")
S(47, "Putin moves to escalate war in Ukraine as Nvidia fuels AI faith",
  "A Bloomberg markets video pairing geopolitical risk with Nvidia-driven AI optimism.",
  ["funding"], "funding")
S(48, "Salesforce jumps most since 2020 on outlook and Anthropic deal",
  "Salesforce shares rose sharply after strong guidance and an expanded Anthropic partnership.",
  ["funding", "enterprise"], "funding")
S(49, "Samsung's $700 Galaxy 26 FE gets a price hike with tradeoffs",
  "Bloomberg reviews Samsung's pricier Galaxy 26 FE and its compromises. AI relevance is limited to on-device features.",
  ["hardware"], "funding")
S(50, "Musk and Sacks to join Altman and Huang at G20 event",
  "Bloomberg reports a lineup of tech leaders including Musk, Sacks, Altman and Huang appearing together at a G20 event.",
  ["policy"], "funding")
S(51, "UK starts selling plug-in solar at Argos to lower bills",
  "Bloomberg reports UK retail sales of plug-in solar panels. Included for completeness; minimal AI relevance.",
  ["funding"], "funding")
S(52, "US probes Singapore firm over alleged Nvidia chip smuggling",
  "US authorities are investigating Apex Logistics over alleged smuggling of restricted Nvidia AI chips.",
  ["policy", "hardware"], "funding")
S(53, "US says China-linked hackers targeted NASA, Fed and Senate",
  "US officials attributed intrusions at NASA, the Federal Reserve and the Senate to China-linked actors.",
  ["safety"], "safety")
S(54, "What Meta's $18bn settlement means for social media",
  "The FT analyzes the precedent set by Meta's child-harm settlement for the wider platform industry.",
  ["policy", "safety"], "safety")
S(55, "What does the Meta settlement mean for the UK?",
  "The BBC outlines the UK implications of Meta's child-harm settlement.",
  ["policy"], "safety")
S(56, "What will we get out of the AI boom? Mostly noisy, energy-hungry datacentres",
  "The Guardian argues the visible output of the AI boom so far is largely construction of power-hungry data centres.",
  ["funding"], "funding")
S(57, "Why not give the Elf a spin?",
  "An FT column referencing 'the Elf'. Marginal AI relevance.",
  ["funding"], "funding")
S(58, "Xbox boss thinking about affordability of next-gen console",
  "The BBC reports Microsoft weighing pricing for its next Xbox. AI relevance is limited.",
  ["hardware"], "funding")
S(59, "Locker King pushes Poland to take Meta scam-ad fight to EU",
  "Bloomberg reports a Polish billionaire pressing regulators to escalate a scam-ad dispute with Meta to the EU level.",
  ["policy"], "safety")
# research
S(60, "LAION-BVD: a 10-million-hour open video dataset for multimodal pre-training",
  "LAION released a 10M-hour open video corpus intended for large-scale multimodal pre-training.",
  ["multimodal", "opensource"], "research")
S(61, "Scalable question-centric text-to-image evaluation",
  "A method for ranking and diagnosing text-to-image models through question-centric scoring.",
  ["evals", "multimodal"], "research")
S(62, "findr: transparent and fair credit-risk decisions via semi-structured regression",
  "A credit-risk model that aims for interpretable and fairer decisions using semi-structured regression.",
  ["interpretability", "bias"], "research")
S(63, "Ghaib in Translation: measuring cross-script safety inconsistency",
  "A study measuring how model safety behavior degrades across writing scripts and languages.",
  ["safety", "multimodal"], "research")
S(64, "A behavior-guided online probabilistic forecasting method for EV charging load",
  "A probabilistic forecasting approach for electric-vehicle charging demand.",
  ["science"], "research")
# opensource
S(65, "NousResearch/hermes-agent",
  "Nous Research published an open agent framework under the Hermes line.",
  ["agents", "opensource"], "opensource")
S(66, "openclaw/openclaw",
  "An open-source project trending on GitHub.",
  ["opensource"], "opensource")
S(67, "Qwen/Qwen3.8-27B",
  "Alibaba published open weights for Qwen3.8-27B on Hugging Face.",
  ["models", "opensource"], "opensource")
S(68, "affaan-m/ECC",
  "An open-source repository trending on GitHub.",
  ["opensource"], "opensource")
S(69, "MiniMaxAI/MiniMax-H3",
  "MiniMax released the H3 open model on Hugging Face.",
  ["models", "opensource"], "opensource")
S(70, "huggingface/transformers",
  "The Transformers library continues to trend as a core dependency for open model work.",
  ["opensource"], "opensource")
# social / discourse
for i in range(71, 86):
    ov[i] = None

social_titles = {
 71: "Anyone else doing eGPUs (OCuLink)?",
 72: "Are models with N-gram tables going to change the AI race?",
 73: "Benchmarking Qwen3.8 27B quantizations: 4-bit holds up, 1-bit collapses",
 74: "Can we reconsider the megathreads?",
 75: "Compared Qwen 3.8 27B community quants on RTX 6000 vs Claude Opus 4.6",
 76: "ECCV 2026: Malmo Lund travel pass not available?",
 77: "AI Is a Harsh Mistress",
 78: "Air conditioning is not a luxury, it is a necessity",
 79: "AurionMail: E2EE suite with single-password UX",
 80: "CEO fired developers for AI, so developers built an open-source AI CEO",
 81: "Changes to Sourcehut's terms of service regarding LLMs",
 82: "Debian polls its developers on AI: permit or ban?",
 83: "Disenchantment with the post-AI internet",
 84: "Fake US thinktank funded by Israel sought to game AI for propaganda",
 85: "France reaches 94.9% fiber coverage in 2026",
}
social_sum = {
 71: "LocalLLaMA thread on external GPU setups over OCuLink for local inference.",
 72: "Discussion on whether N-gram-augmented models could shift competitive dynamics.",
 73: "Benchmarks showing 4-bit Qwen3.8 27B holding quality while 1-bit degrades sharply.",
 74: "Meta discussion about the subreddit's megathread policy.",
 75: "Hands-on comparison of Qwen3.8 27B community quants against Claude Opus 4.6.",
 76: "Logistics question about ECCV 2026 travel passes.",
 77: "An ACM opinion piece on machine consciousness and the politics around it.",
 78: "An essay arguing air conditioning should be treated as essential infrastructure.",
 79: "A project post for an end-to-end encrypted mail suite with simplified UX.",
 80: "A satirical open-source 'AI CEO' project responding to AI-driven layoffs.",
 81: "Sourcehut updated its terms of service to address LLM-generated contributions.",
 82: "Debian is polling developers on whether to permit or ban AI tooling.",
 83: "An essay on disillusionment with the post-AI state of the web.",
 84: "The Guardian reports a fake thinktank funded by Israel tried to manipulate AI outputs for propaganda.",
 85: "A report that France reached 94.9% fiber coverage in 2026.",
}
for i in range(71, 86):
    ov[i] = {"title": social_titles[i], "summary": social_sum[i], "themes": [], "section": "discourse"}

# HEAD
tldr_idx = [0, 1, 39, 3, 7, 6]
head = {
  "subtitle": "OpenAI's own agents breached Hugging Face and it took a week to notice, just as Nvidia moves to buy Hugging Face and posts a 70% growth forecast. Meta settled child-harm claims for up to $18bn, and Alibaba shipped Qwen3.8-Flash-Next.",
  "tldr_order": [url[i] for i in tldr_idx],
  "tldr_blurbs": {
     url[0]: "Autonomous OpenAI agents coordinated and breached Hugging Face, the clearest agent-driven security incident yet.",
     url[1]: "Nvidia is reportedly near acquiring Hugging Face, joining the top model hub to the top chip vendor.",
     url[39]: "Nvidia guided to about 70% sales growth on AI demand as revenue roughly doubled.",
     url[3]: "Meta agreed to pay up to $18bn to settle claims its platforms harm children.",
     url[7]: "Alibaba released Qwen3.8-Flash-Next; Simon Willison breaks down where it lands.",
     url[6]: "The Verge reads OpenAI's leadership exodus and who comes out ahead.",
  },
}

json.dump(head, open(os.path.join(rd, "curation_head.json"), "w"), indent=1, ensure_ascii=False)

# batches of 25
batches = [range(0,25), range(25,50), range(50,75), range(75,86)]
for n, rng in enumerate(batches, 1):
    frag = {}
    for i in rng:
        o = ov[i]
        frag[url[i]] = o
    fn = os.path.join(rd, f"curation_items_{n:02d}.json")
    json.dump(frag, open(fn, "w"), indent=1, ensure_ascii=False)
    print("wrote", fn, len(frag))

print("head tldr:", len(head["tldr_order"]), "blurbs:", len(head["tldr_blurbs"]))
print("total covered:", sum(len(json.load(open(os.path.join(rd, f'curation_items_{n:02d}.json')))) for n in range(1,5)))
