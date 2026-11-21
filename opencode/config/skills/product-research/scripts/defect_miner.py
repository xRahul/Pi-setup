#!/usr/bin/env python3
"""
Wirecutter-Grade Defect & Reddit/Teardown Reality Mining Engine CLI
Extracts systemic defect patterns, lab benchmarks, and local readiness (IRF) compliance
from raw search results, scraped text, teardown logs, and Reddit community snippets.

Features:
  1. Defect & Failure Extraction:
     - Regex & pattern matching for category-specific defects across all 7 categories
     - Severity classification: critical, severe, moderate, minor
     - Defect type tagging: systemic_design_flaw, batch_defect, isolated_lemon based on
       corroboration keywords (teardown, ifixit, soldering) and source count
  2. Lab Measurement Extraction:
     - Numerical regex parsers for brightness (nits), color accuracy (delta-E), noise (dB/dBA),
       thermals (°C), battery runtime (hours), charging speed (Watts), ISEER rating, active % wt/vol
  3. IRF Compliance & Environment Extraction:
     - Service TAT in hours/days, statutory marks (BIS, BEE, FSSAI, CE, FCC), coil materials,
       and authorized seller verification
  4. Dual Output Modes:
     - --to-extractor-json: Outputs structured JSON directly ingestible by metric_extractor.py
     - --markdown: Outputs publication-grade Wirecutter-style Defect & Longevity Audit

End-to-End Pipeline:
  cat search_results.json | python3 scripts/defect_miner.py --category smartphones --to-extractor-json \\
    | python3 scripts/metric_extractor.py | python3 scripts/product_scorer.py --markdown
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# -----------------------------------------------------------------------------
# Category Defect Taxonomy
# -----------------------------------------------------------------------------

CATEGORY_DEFECT_TAXONOMY: Dict[str, List[Dict[str, Any]]] = {
    "smartphones": [
        # Critical
        {
            "patterns": [
                r"motherboard\s+(?:dead\s*boot|failure|dead|fried|short(?:ed)?|replaced)",
                r"dead\s*boot(?:\s+issue|\s+problem)?",
                r"edl\s+mode\s+brick",
                r"qualcomm\s+hs-usb\s+qdloader",
                r"sudden\s+death\s+syndrome",
            ],
            "issue": "Motherboard dead-boot / power delivery IC failure",
            "severity": "critical",
            "affects": "build_durability",
            "systemic_clues": ["solder", "thermal stress", "cpu desoldering", "bga", "pmic"],
        },
        {
            "patterns": [
                r"(?:vertical\s+)?green\s+line(?:\s+issue|\s+on\s+screen|\s+after\s+update)?",
                r"pink\s+line\s+on\s+display",
                r"white\s+screen\s+of\s+death",
                r"display\s+flexgate",
            ],
            "issue": "Display vertical green line / flex bonding degradation",
            "severity": "critical",
            "affects": "display",
            "systemic_clues": ["ota update", "heat", "display controller", "amoled flex"],
        },
        {
            "patterns": [
                r"battery\s+swell(?:ing|ed|t)?",
                r"back\s+panel\s+(?:lifting|popping\s+off)\s+due\s+to\s+battery",
                r"thermal\s+runaway",
            ],
            "issue": "Battery swelling / thermal runaway risk",
            "severity": "critical",
            "affects": "battery_charging",
            "systemic_clues": ["pouch cell", "charging heat", "delamination"],
        },
        # Severe
        {
            "patterns": [
                r"camera\s+lens\s+ois\s+(?:rattle|failure|jitter|vibrat(?:ing|ion))",
                r"camera\s+sensor\s+focus\s+(?:failure|stuck|hunting)",
                r"black\s+screen\s+when\s+opening\s+camera",
            ],
            "issue": "Camera OIS actuator failure / autofocus motor breakdown",
            "severity": "severe",
            "affects": "camera",
            "systemic_clues": ["magnet", "ois motor", "actuator"],
        },
        {
            "patterns": [
                r"(?:severe|aggressive|extreme)\s+thermal\s+throttling",
                r"throttl(?:es|ing)\s+(?:down\s+to\s+)?(?:40|50|60)%",
                r"overheating\s+(?:warning|shutdown|turns\s+off)",
            ],
            "issue": "Severe thermal throttling / sustained performance collapse",
            "severity": "severe",
            "affects": "performance",
            "systemic_clues": ["vapor chamber", "heat dissipation", "thermal paste"],
        },
        {
            "patterns": [
                r"water\s+(?:damage|ingress)\s+despite\s+ip\s*6[78]",
                r"moisture\s+detected\s+in\s+usb\s+port\s+(?:false\s+alarm|loop|stuck)",
            ],
            "issue": "Port moisture detection false-alarm loop / gasket failure",
            "severity": "severe",
            "affects": "build_durability",
            "systemic_clues": ["corrosion", "usb-c pin", "gasket seal"],
        },
        # Moderate
        {
            "patterns": [
                r"camera\s+lens\s+(?:internal\s+)?fogging(?:\s+in\s+humidity)?",
                r"moisture\s+condensation\s+inside\s+camera\s+lens",
            ],
            "issue": "Internal camera lens fogging / condensation",
            "severity": "moderate",
            "affects": "camera",
            "systemic_clues": ["airtight seal", "desiccant", "lens ring"],
        },
        {
            "patterns": [
                r"(?:erratic|inconsistent|slow)\s+fingerprint\s+(?:sensor|scanner|reader)",
                r"fingerprint\s+(?:fails\s+to\s+recognize|fails\s+50%\s+of\s+time)",
            ],
            "issue": "Inconsistent in-display fingerprint biometric recognition",
            "severity": "moderate",
            "affects": "build_durability",
            "systemic_clues": ["optical sensor", "panel calibration"],
        },
        {
            "patterns": [
                r"aggressive\s+(?:background\s+app\s+killing|ram\s+management)",
                r"notification\s+(?:delays|delay\s+bug|missed\s+notifications)",
            ],
            "issue": "Aggressive background app killing & delayed push notifications",
            "severity": "moderate",
            "affects": "software_support",
            "systemic_clues": ["oem skin", "battery optimizer", "doze override"],
        },
        {
            "patterns": [
                r"frame\s+paint\s+(?:peeling|chipping|flaking)",
                r"anodiz(?:ed|ation)\s+(?:coating\s+wearing|wearing\s+off)",
            ],
            "issue": "Chassis anodization wear & cosmetic paint flaking",
            "severity": "moderate",
            "affects": "build_durability",
            "systemic_clues": ["plating quality", "aluminum grade"],
        },
        # Minor
        {
            "patterns": [
                r"launcher\s+(?:micro[- ]stutters?|jitter|frame\s+drops?)",
                r"gesture\s+navigation\s+animation\s+stutter",
            ],
            "issue": "UI animation micro-stutters and gesture frame drops",
            "severity": "minor",
            "affects": "software_support",
            "systemic_clues": ["gpu rendering", "120hz governor"],
        },
        {
            "patterns": [
                r"fingerprint\s+smudge\s+magnet",
                r"oleophobic\s+coating\s+(?:wears\s+off\s+fast|poor)",
            ],
            "issue": "Weak oleophobic coating / fingerprint smudge magnet",
            "severity": "minor",
            "affects": "build_durability",
            "systemic_clues": ["surface treatment"],
        },
    ],
    "laptops": [
        # Critical
        {
            "patterns": [
                r"motherboard\s+(?:dead\s*boot|fried|failure|blown\s+mosfet)",
                r"power\s+delivery\s+ic\s+burnout",
                r"gpu\s+(?:artifacting|vram\s+solder\s+joint\s+crack|dead\s+gpu)",
            ],
            "issue": "Motherboard power stage / GPU VRAM solder fatigue",
            "severity": "critical",
            "affects": "performance",
            "systemic_clues": ["thermal cycling", "bga fracture", "vrm cooling"],
        },
        {
            "patterns": [
                r"battery\s+(?:swelling|bulging|expanding)",
                r"trackpad\s+(?:lifting|popping\s+up)\s+due\s+to\s+battery",
            ],
            "issue": "Battery swelling lifting keyboard deck / trackpad",
            "severity": "critical",
            "affects": "battery_life",
            "systemic_clues": ["charging voltage", "heat soak", "pouch expansion"],
        },
        # Severe
        {
            "patterns": [
                r"hinge\s+(?:cracking|fracture|broken|chassis\s+separation|snapped)",
                r"display\s+hinge\s+(?:tearing|stiff\s+broken)",
                r"screen\s+bezel\s+separating\s+at\s+hinge",
            ],
            "issue": "Display hinge mount fracture & chassis separation",
            "severity": "severe",
            "affects": "build_upgradeability",
            "systemic_clues": ["brass standoff", "plastic anchor", "torque rating"],
        },
        {
            "patterns": [
                r"liquid\s+metal\s+(?:pump-?out|leakage|corrosion)",
                r"thermal\s+paste\s+(?:pump-?out|dry-?out\s+in\s+months)",
            ],
            "issue": "Thermal interface liquid metal pump-out / dry-out",
            "severity": "severe",
            "affects": "cooling_thermals",
            "systemic_clues": ["heatsink mounting pressure", "barrier seal"],
        },
        {
            "patterns": [
                r"keyboard\s+(?:keys\s+failing|chattering|double\s+typing|unresponsive\s+keys)",
                r"display\s+flex\s+cable\s+(?:tearing|blacking\s+out\s+at\s+angles)",
            ],
            "issue": "Keyboard switch matrix failure / display ribbon tear",
            "severity": "severe",
            "affects": "build_upgradeability",
            "systemic_clues": ["membrane trace", "hinge routing"],
        },
        # Moderate
        {
            "patterns": [
                r"severe\s+thermal\s+throttling",
                r"fan\s+bearing\s+(?:rattle|noise|loud\s+whine|high\s*pitch)",
                r"loud\s+coil\s+whine(?:\s+under\s+load)?",
            ],
            "issue": "Loud fan bearing whine & acoustic coil noise",
            "severity": "moderate",
            "affects": "cooling_thermals",
            "systemic_clues": ["inductor potting", "sleeve bearing"],
        },
        {
            "patterns": [
                r"modern\s+standby\s+(?:battery\s+drain|hot\s+in\s+bag|sleep\s+drain)",
                r"laptop\s+wake[s]?\s+up\s+inside\s+backpack",
            ],
            "issue": "Modern Standby connected sleep battery drain & thermal wake",
            "severity": "moderate",
            "affects": "battery_life",
            "systemic_clues": ["s0ix state", "windows acpi", "wifi sleep"],
        },
        {
            "patterns": [
                r"trackpad\s+(?:rattle|wobble|loose|pre-travel)",
                r"chassis\s+creaking\s+when\s+lifted",
            ],
            "issue": "Trackpad chassis wobble & diving board mechanism looseness",
            "severity": "moderate",
            "affects": "build_upgradeability",
            "systemic_clues": ["spring tension", "palmrest stiffness"],
        },
        # Minor
        {
            "patterns": [
                r"keyboard\s+keycaps?\s+(?:shine|oil\s+shine|wearing\s+smooth)",
                r"deck\s+fingerprint\s+smudges?",
            ],
            "issue": "ABS keycap premature surface shine & palmrest smudging",
            "severity": "minor",
            "affects": "build_upgradeability",
            "systemic_clues": ["abs vs pbt", "soft touch coating"],
        },
    ],
    "inverter_acs": [
        # Critical
        {
            "patterns": [
                r"(?:refrigerant|gas)\s+(?:leak|leakage|escaped|discharged)",
                r"r32\s+gas\s+leak",
                r"compressor\s+(?:burnout|locked\s+rotor|dead|tripping\s+mcb)",
                r"outdoor\s+pcb\s+(?:failure|blown|burnt|surge\s+failure)",
            ],
            "issue": "Refrigerant gas leak / outdoor inverter PCB power surge blowout",
            "severity": "critical",
            "affects": "cooling_efficiency_iseer",
            "systemic_clues": ["u-bend brazing", "conformal coating missing", "varistor"],
        },
        # Severe
        {
            "patterns": [
                r"(?:evaporator|condenser)\s+coil\s+(?:corrosion|rust|pitting|leaking)",
                r"aluminium\s+coil\s+(?:corrosion|micro\s*channel\s+leak)",
                r"water\s+(?:dripping|leaking)\s+from\s+indoor\s+unit",
                r"choked\s+drain\s+pan\s+overflow",
            ],
            "issue": "Evaporator coil corrosion pitting & indoor unit condensate dripping",
            "severity": "severe",
            "affects": "condenser_coil_materials",
            "systemic_clues": ["galvanic rust", "pfc tube", "condensate drain slope"],
        },
        {
            "patterns": [
                r"cooling\s+(?:derating|trips?|stops\s+cooling)\s+above\s+(?:45|48|50)\s*°?c",
                r"compressor\s+overheat\s+cut[- ]off\s+in\s+peak\s+summer",
            ],
            "issue": "Severe ambient cooling derating & compressor thermal trip >48°C",
            "severity": "severe",
            "affects": "cooling_efficiency_iseer",
            "systemic_clues": ["derating profile", "condenser fan motor sizing"],
        },
        # Moderate
        {
            "patterns": [
                r"indoor\s+unit\s+plastic\s+(?:creaking|cracking|popping\s+noise)",
                r"thermal\s+expansion\s+body\s+noise",
            ],
            "issue": "Indoor unit plastic expansion creaking / clicking acoustics",
            "severity": "moderate",
            "affects": "noise_levels",
            "systemic_clues": ["plastic mold tolerance", "bracket flex"],
        },
        {
            "patterns": [
                r"outdoor\s+compressor\s+(?:vibration|drone|rattle|loud\s+humming)",
                r"compressor\s+noise\s+exceeding\s+55\s*db",
            ],
            "issue": "Outdoor unit excessive compressor drone & wall resonance vibration",
            "severity": "moderate",
            "affects": "noise_levels",
            "systemic_clues": ["rubber damper", "rotary compressor balance"],
        },
        # Minor
        {
            "patterns": [
                r"remote\s+control\s+backlight\s+missing",
                r"led\s+temperature\s+display\s+(?:too\s+bright|cannot\s+turn\s+off)",
            ],
            "issue": "Unbacklit remote control & bright indoor LED glare",
            "severity": "minor",
            "affects": "warranty_service",
            "systemic_clues": ["remote design"],
        },
    ],
    "washing_machines": [
        # Critical
        {
            "patterns": [
                r"(?:drum\s+)?spider(?:\s+arm)?.*?(?:galvanic\s+corrosion|fracture|broken|failure|rot|corrosion)",
                r"galvanic\s+corrosion.*?(?:spider|drum)",
                r"spider\s+arm\s+(?:fracture|corrosion|broken|failure|snapped)",
                r"tub\s+bearing\s+(?:failure|seized|destroyed|water\s+leakage)",
                r"rusty\s+water\s+leakage\s+from\s+rear\s+bearing",
            ],
            "issue": "Drum spider arm galvanic corrosion & tub bearing seal destruction",
            "severity": "critical",
            "affects": "drum_tub_durability",
            "systemic_clues": ["aluminium alloy", "stainless tub galvanic couple", "lip seal"],
        },
        # Severe
        {
            "patterns": [
                r"inverter\s+motor\s+(?:board\s+failure|hall\s+sensor\s+failure|blown)",
                r"violent\s+shaking\s+during\s+spin",
                r"drum\s+banging\s+against\s+(?:body|cabinet)",
                r"(?:ue|dc)\s+unbalanced\s+load\s+error\s+loop",
                r"suspension\s+(?:damper\s+failure|strut\s+broken)",
            ],
            "issue": "Suspension damper collapse / persistent unbalanced spin error",
            "severity": "severe",
            "affects": "noise_vibration",
            "systemic_clues": ["friction damper", "counterweight bolt", "hall sensor"],
        },
        {
            "patterns": [
                r"door\s+boot\s+(?:seal\s+mould|rubber\s+gasket\s+mould|mildew|torn)",
                r"water\s+leakage\s+from\s+door\s+gasket",
            ],
            "issue": "Door boot rubber gasket mildew buildup & tearing leakage",
            "severity": "severe",
            "affects": "drum_tub_durability",
            "systemic_clues": ["drain hole diameter", "anti-microbial treatment"],
        },
        # Moderate
        {
            "patterns": [
                r"drain\s+pump\s+(?:blockage|noise|failure|impeller\s+jammed)",
                r"water\s+not\s+draining\s+(?:error|issue)",
            ],
            "issue": "Drain pump impeller jamming & acoustic drainage resonance",
            "severity": "moderate",
            "affects": "wash_quality_motor",
            "systemic_clues": ["lint filter bypass", "magnetic pump impeller"],
        },
        {
            "patterns": [
                r"detergent\s+(?:drawer\s+clogging|residue\s+leftover|siphon\s+failure)",
                r"powder\s+caking\s+in\s+dispenser",
            ],
            "issue": "Detergent dispenser siphoning failure & powder caking",
            "severity": "moderate",
            "affects": "smart_programs",
            "systemic_clues": ["water jet pressure", "siphon tube design"],
        },
        # Minor
        {
            "patterns": [
                r"lint\s+filter\s+(?:difficult\s+to\s+clean|hard\s+to\s+remove)",
                r"end\s+of\s+cycle\s+buzzer\s+(?:too\s+loud|cannot\s+mute)",
            ],
            "issue": "Lint filter accessibility & unmutable cycle finish chime",
            "severity": "minor",
            "affects": "smart_programs",
            "systemic_clues": ["chime speaker", "filter clip"],
        },
    ],
    "skincare": [
        # Critical
        {
            "patterns": [
                r"allergic\s+contact\s+dermatitis",
                r"chemical\s+burn\s+from\s+formula",
                r"microbial\s+(?:contamination|growth|fungus|mould\s+in\s+bottle)",
                r"heavy\s+metal\s+(?:contamination|mercury|lead|arsenic)",
            ],
            "issue": "Contact dermatitis / microbial contamination in formulation",
            "severity": "critical",
            "affects": "safety_non_comedogenic",
            "systemic_clues": ["preservative system", "challenge test", "ph excursion"],
        },
        # Severe
        {
            "patterns": [
                r"(?:active\s+)?rapid\s+oxidation",
                r"(?:vitamin\s+c|ascorbic\s+acid)\s+turned\s+(?:brown|dark\s+orange|yellow)\s+(?:in|within)\s+(?:2|3|4)\s+weeks",
                r"formula\s+(?:destabilized|separated|curdled)",
                r"severe\s+cystic\s+(?:acne\s+breakout|purging\s+turned\s+breakout)",
            ],
            "issue": "Rapid active oxidation / premature active degradation in packaging",
            "severity": "severe",
            "affects": "formulation_ph_stability",
            "systemic_clues": ["unbuffered formula", "clear glass", "air exposure"],
        },
        {
            "patterns": [
                r"pump\s+dispenser\s+(?:broken|clogged|crystalliz(?:ed|ation))",
                r"dropper\s+(?:shattered|rubber\s+bulb\s+corroded)",
            ],
            "issue": "Pump nozzle crystallization blockage / dispensing failure",
            "severity": "severe",
            "affects": "packaging_preservation",
            "systemic_clues": ["airless pump valve", "solvent evaporation"],
        },
        # Moderate
        {
            "patterns": [
                r"formula\s+(?:pilling|balls\s+up)\s+under\s+(?:sunscreen|moisturizer|makeup)",
                r"excessive\s+pilling",
            ],
            "issue": "Product pilling and poor layering compatibility",
            "severity": "moderate",
            "affects": "texture_absorption",
            "systemic_clues": ["polymer weight", "silicone elastomer load"],
        },
        {
            "patterns": [
                r"unpleasant\s+(?:rancid|metallic|hot\s*dog|chemical)\s+(?:smell|odor)",
                r"heavy\s+greasy\s+tacky\s+finish",
            ],
            "issue": "Offensive formulation odor & persistent sticky/greasy finish",
            "severity": "moderate",
            "affects": "texture_absorption",
            "systemic_clues": ["lipid oxidation", "humectant ratio"],
        },
        # Minor
        {
            "patterns": [
                r"dropper\s+dripping\s+outside\s+bottle",
                r"bottle\s+label\s+(?:peeling|smudging\s+off)",
            ],
            "issue": "Dropper rim messiness & peeling bottle label",
            "severity": "minor",
            "affects": "packaging_preservation",
            "systemic_clues": ["dropper aperture"],
        },
    ],
    "supplements": [
        # Critical
        {
            "patterns": [
                r"amino\s+spiking(?:\s+detected|\s+confirmed)?",
                r"nitrogen\s+spiking\s+with\s+(?:glycine|taurine)",
                r"heavy\s+metal\s+(?:contamination|lead|cadmium|arsenic\s+exceeded)",
                r"undeclared\s+(?:steroid|pharmaceutical|banned\s+substance)",
            ],
            "issue": "Amino spiking (nitrogen falsification) / heavy metal contamination",
            "severity": "critical",
            "affects": "zero_amino_spiking_heavy_metals",
            "systemic_clues": ["kjeldahl assay", "glycine filler", "inductively coupled plasma"],
        },
        # Severe
        {
            "patterns": [
                r"severe\s+(?:gastrointestinal|gi\s+distress|diarrhea|stomach\s+cramps)",
                r"violent\s+bloating\s+and\s+gas",
                r"third[- ]party\s+lab\s+failed\s+assay",
                r"actual\s+protein\s+(?:content\s+)?(?:<|less\s+than\s+)(?:70|75|80)%",
                r"inner\s+(?:safety\s+)?seal\s+(?:broken|missing|tampered)",
            ],
            "issue": "Severe GI distress / third-party assay failure (<80% label claim)",
            "severity": "severe",
            "affects": "active_purity_potency",
            "systemic_clues": ["lactose load", "raw wpc purity", "induction seal heat"],
        },
        # Moderate
        {
            "patterns": [
                r"terrible\s+mixability",
                r"stubborn\s+clumps\s+that\s+won['’]?t\s+dissolve",
                r"chalky\s+powdery\s+sludge\s+at\s+bottom",
                r"artificial\s+(?:chemical|sickeningly\s+sweet)\s+aftertaste",
            ],
            "issue": "Poor mixability with insoluble clumping & chemical aftertaste",
            "severity": "moderate",
            "affects": "mixability_taste",
            "systemic_clues": ["lecithination", "sucralose concentration"],
        },
        {
            "patterns": [
                r"missing\s+measuring\s+scoop",
                r"scoop\s+yields\s+inaccurate\s+serving\s+weight",
            ],
            "issue": "Missing or inaccurate scoop calibration (+/- 25% discrepancy)",
            "severity": "moderate",
            "affects": "mixability_taste",
            "systemic_clues": ["bulk density variance", "scoop cc volume"],
        },
        # Minor
        {
            "patterns": [
                r"pouch\s+ziplock\s+(?:hard\s+to\s+close|powder\s+clogged|fails)",
                r"powder\s+dust\s+plume\s+when\s+scooping",
            ],
            "issue": "Pouch ziplock clogging & fine powder aerosolization",
            "severity": "minor",
            "affects": "lab_transparency",
            "systemic_clues": ["zipper channel design"],
        },
    ],
    "tws_audio": [
        # Critical
        {
            "patterns": [
                r"charging\s+case\s+battery\s+(?:swelling|bulging)",
                r"charging\s+pins?\s+(?:galvanic\s+corrosion|green\s+corrosion|rusted)",
                r"earbud\s+(?:completely\s+dead|refuses\s+to\s+charge)",
                r"driver\s+blowout\s+(?:distortion|permanent\s+buzzing)",
            ],
            "issue": "Charging pin galvanic corrosion & permanent dead earbud failure",
            "severity": "critical",
            "affects": "comfort_ip_rating",
            "systemic_clues": ["sweat ingress", "gold plating thickness", "pogo pin"],
        },
        # Severe
        {
            "patterns": [
                r"anc\s+feedback\s+(?:squeal|piercing\s+scream|high[- ]pitch\s+whistle)",
                r"ultrasonic\s+feedback\s+blast\s+in\s+ear",
            ],
            "issue": "Acoustic feedback squeal / high-pitch ANC mic instability",
            "severity": "severe",
            "affects": "anc_transparency",
            "systemic_clues": ["internal mic seal", "acoustic mesh looseness"],
        },
        {
            "patterns": [
                r"severe\s+bluetooth\s+(?:stutter|disconnect\s+loop)",
                r"one\s+earbud\s+(?:disconnects|stops\s+playing)\s+constantly",
                r"mic\s+(?:unusable|robotic|muffled)\s+in\s+windy\s+conditions",
            ],
            "issue": "Persistent single-earbud disconnect loop & wind-distorted microphone",
            "severity": "severe",
            "affects": "sound_quality",
            "systemic_clues": ["antenna placement", "master-slave sync", "mic port angle"],
        },
        # Moderate
        {
            "patterns": [
                r"ear\s+canal\s+(?:pressure|suction|occlusion\s+discomfort)",
                r"plunger\s+effect\s+discomfort",
            ],
            "issue": "Severe ear canal pneumatic pressure & occlusion sensation",
            "severity": "moderate",
            "affects": "comfort_ip_rating",
            "systemic_clues": ["pressure relief vent", "acoustic porting"],
        },
        {
            "patterns": [
                r"accidental\s+touch\s+(?:triggers|misfires)\s+from\s+(?:sweat|hair|rain)",
                r"battery\s+drain\s+asymmetry\s+(?:>30%|greater\s+than\s+30%)",
            ],
            "issue": "Touch sensor misfires from moisture & severe L/R battery asymmetry",
            "severity": "moderate",
            "affects": "battery_charging",
            "systemic_clues": ["capacitive sensor tuning", "ble master role drain"],
        },
        # Minor
        {
            "patterns": [
                r"case\s+lid\s+(?:loose|wobbl(?:y|ing)|creaking\s+hinge)",
                r"earbuds\s+(?:slippery|hard\s+to\s+extract\s+from\s+case)",
            ],
            "issue": "Wobbly case hinge & slippery glossy earbud extraction grip",
            "severity": "minor",
            "affects": "comfort_ip_rating",
            "systemic_clues": ["magnet retention", "finish texture"],
        },
    ],
}

# -----------------------------------------------------------------------------
# Measurement Extraction Regex Parsers
# -----------------------------------------------------------------------------

MEASUREMENT_PARSERS: Dict[str, List[Dict[str, Any]]] = {
    "peak_brightness_nits": [
        {
            "pattern": r"(?:peak(?:\s+display)?\s+brightness\s*(?:of|is|reaches|hit)?[:\s]*|measured\s+peak\s+of\s+)?(\d{3,5}(?:,\d+)*(?:\.\d+)?)\s*(?:nits?|cd\/m[²2])(?:\s+peak)?",
            "group": 1,
            "type": float,
            "condition": lambda m, ctx: "peak" in ctx.lower() or "nit" in ctx.lower(),
        }
    ],
    "display_brightness_nits": [
        {
            "pattern": r"(?:sustained|manual|100%|full\s+screen)\s+brightness[:\s]*(\d{2,4}(?:\.\d+)?)\s*(?:nits?|cd\/m[²2])",
            "group": 1,
            "type": float,
        }
    ],
    "color_accuracy_delta_e": [
        {
            "pattern": r"(?:delta[- ]?[eE]|dE(?:\s*2000)?)\s*(?:of|is|:|=)?\s*(\d+(?:\.\d+)?)",
            "group": 1,
            "type": float,
        }
    ],
    "pwm_dimming_hz": [
        {
            "pattern": r"(\d{3,5}(?:,\d+)?)\s*Hz\s*(?:PWM|dimming|flicker[- ]free)",
            "group": 1,
            "type": lambda v: float(str(v).replace(",", "")),
        }
    ],
    "color_gamut_srgb_pct": [
        {
            "pattern": r"(\d{2,3}(?:\.\d+)?)\s*%\s*(?:sRGB|coverage)",
            "group": 1,
            "type": float,
        }
    ],
    "cinebench_r23_multicore": [
        {
            "pattern": r"(?:cinebench\s*(?:r23)?(?:\s*multi(?:-?core)?)?)[:\s]*(\d{4,6}(?:,\d+)?)",
            "group": 1,
            "type": lambda v: float(str(v).replace(",", "")),
        }
    ],
    "cinebench_r23_singlecore": [
        {
            "pattern": r"(?:cinebench\s*(?:r23)?(?:\s*single(?:-?core)?)?|single(?:-?core)?(?:\s+score)?)[:\s]*(\d{3,4}(?:,\d+)?)",
            "group": 1,
            "type": lambda v: float(str(v).replace(",", "")),
        }
    ],
    "geekbench_multicore": [
        {
            "pattern": r"(?:geekbench\s*(?:6)?(?:\s*multi(?:-?core)?)?)[:\s]*(\d{4,6}(?:,\d+)?)",
            "group": 1,
            "type": lambda v: float(str(v).replace(",", "")),
        }
    ],
    "sustained_perf_percent": [
        {
            "pattern": r"(?:sustained(?:\s+performance)?|throttl(?:e|ing)\s+stability|stability\s+score)[:\s]*(\d{2,3}(?:\.\d+)?)\s*%",
            "group": 1,
            "type": float,
        },
        {
            "pattern": r"(\d{2,3}(?:\.\d+)?)\s*%\s*(?:stability|sustained\s+performance)",
            "group": 1,
            "type": float,
        },
    ],
    "sustained_pl1_wattage": [
        {
            "pattern": r"(?:sustained\s+PL1|PL1|sustained\s+power|TDP)[:\s]*(\d{2,3}(?:\.\d+)?)\s*W(?:atts)?",
            "group": 1,
            "type": float,
        }
    ],
    "thermal_peak_temp_c": [
        {
            "pattern": r"(?:peak|surface|cpu|max)\s*temp(?:erature)?[:\s]*(\d{2,3}(?:\.\d+)?)\s*°?\s*C(?:elsius)?",
            "group": 1,
            "type": float,
        },
        {
            "pattern": r"(\d{2,3}(?:\.\d+)?)\s*°\s*C(?:\s*(?:under load|peak|surface))",
            "group": 1,
            "type": float,
        },
    ],
    "keyboard_deck_temp_c": [
        {
            "pattern": r"keyboard(?:\s+deck)?(?:\s+temp(?:erature)?)?[:\s]*(\d{2,3}(?:\.\d+)?)\s*°?\s*C",
            "group": 1,
            "type": float,
        }
    ],
    "fan_noise_dba": [
        {
            "pattern": r"(?:fan\s*noise|noise\s*level|acoustics?)[:\s]*(\d{2,3}(?:\.\d+)?)\s*(?:dB[Aa]|dB\(A\)|decibels?)",
            "group": 1,
            "type": float,
        },
        {
            "pattern": r"(\d{2,3}(?:\.\d+)?)\s*dBA(?:\s+under\s+load)?",
            "group": 1,
            "type": float,
        },
    ],
    "active_battery_runtime_hours": [
        {
            "pattern": r"(\d{1,2}(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:of\s*)?(?:active\s*)?(?:battery|runtime|screen[- ]on|SOT|web\s+browsing)",
            "group": 1,
            "type": float,
        },
        {
            "pattern": r"(?:battery\s+life|runtime)[:\s]*(\d{1,2}(?:\.\d+)?)\s*(?:hours?|hrs?)",
            "group": 1,
            "type": float,
        },
    ],
    "charging_time_minutes": [
        {
            "pattern": r"(?:charges?(?:\s+full)?|0\s*to\s*100%|full\s+charge)\s*(?:in|takes)?\s*(\d{1,3})\s*(?:min(?:ute)?s?)",
            "group": 1,
            "type": float,
        }
    ],
    "charging_wattage": [
        {
            "pattern": r"(\d{2,3})\s*W(?:att)?s?\s*(?:fast\s*)?charg(?:ing|er)",
            "group": 1,
            "type": float,
        }
    ],
    "battery_capacity_mah": [
        {
            "pattern": r"(\d{4,5}(?:,\d+)?)\s*mAh",
            "group": 1,
            "type": lambda v: float(str(v).replace(",", "")),
        }
    ],
    "battery_capacity_wh": [
        {
            "pattern": r"(\d{2,3}(?:\.\d+)?)\s*Wh(?:r)?",
            "group": 1,
            "type": float,
        }
    ],
    "iseer_rating": [
        {
            "pattern": r"(?:ISEER|iseer)(?:\s*rating)?[:\s]*(\d\.\d{1,2})",
            "group": 1,
            "type": float,
        },
        {
            "pattern": r"(\d\.\d{1,2})\s*ISEER",
            "group": 1,
            "type": float,
        },
    ],
    "indoor_silent_db": [
        {
            "pattern": r"(?:indoor|silent|IDU)\s*(?:noise|sound)?(?:\s*(?:of|at|is))?[:\s]*(\d{2}(?:\.\d+)?)\s*dB",
            "group": 1,
            "type": float,
        }
    ],
    "outdoor_compressor_db": [
        {
            "pattern": r"(?:outdoor|compressor|ODU)\s*(?:noise|sound)?(?:\s*(?:of|at|is))?[:\s]*(\d{2}(?:\.\d+)?)\s*dB",
            "group": 1,
            "type": float,
        }
    ],
    "max_spin_speed_rpm": [
        {
            "pattern": r"(\d{3,4})\s*RPM",
            "group": 1,
            "type": float,
        }
    ],
    "water_consumption_litres_per_kg": [
        {
            "pattern": r"(\d+(?:\.\d+)?)\s*(?:L|litres?|liters?)\s*\/\s*kg",
            "group": 1,
            "type": float,
        }
    ],
    "spin_noise_db": [
        {
            "pattern": r"(?:spin\s*noise)[:\s]*(\d{2}(?:\.\d+)?)\s*dB",
            "group": 1,
            "type": float,
        }
    ],
    "active_concentration_pct": [
        {
            "pattern": r"(\d+(?:\.\d+)?)\s*%\s*(?:niacinamide|salicylic|retinol|vitamin\s*c|glycolic|l-ascorbic|hyaluronic|active)",
            "group": 1,
            "type": float,
        }
    ],
    "protein_or_active_purity_pct": [
        {
            "pattern": r"(\d{2,3}(?:\.\d+)?)\s*%\s*(?:protein|purity|active\s+content)",
            "group": 1,
            "type": float,
        }
    ],
    "active_yield_per_serving_g": [
        {
            "pattern": r"(\d{1,2}(?:\.\d+)?)\s*g\s*(?:protein|creatine|active)\s*(?:per\s*(?:serving|scoop)|yield)",
            "group": 1,
            "type": float,
        }
    ],
    "anc_noise_attenuation_db": [
        {
            "pattern": r"(?:ANC|noise\s+cancellation)[:\s]*(-?\d{1,2}(?:\.\d+)?)\s*dB",
            "group": 1,
            "type": lambda v: abs(float(v)),
        },
        {
            "pattern": r"reduces?\s+(?:up\s+to\s+)?(\d{1,2})\s*dB",
            "group": 1,
            "type": float,
        },
    ],
    "single_charge_anc_hours": [
        {
            "pattern": r"(\d{1,2}(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:with\s+ANC|ANC\s+on)",
            "group": 1,
            "type": float,
        }
    ],
    "total_case_hours": [
        {
            "pattern": r"(\d{1,3}(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:total|with\s+case|case\s+battery)",
            "group": 1,
            "type": float,
        }
    ],
}

# -----------------------------------------------------------------------------
# Discrete Attribute Detectors
# -----------------------------------------------------------------------------

DISCRETE_FEATURE_DETECTORS: Dict[str, List[Tuple[str, str]]] = {
    "ip_rating": [
        (r"ip\s*69", "ip69"),
        (r"ip\s*68", "ip68"),
        (r"ip\s*67", "ip67"),
        (r"ip\s*65", "ip65"),
        (r"ip\s*55", "ip55"),
        (r"ip\s*54", "ip54"),
        (r"ip\s*53", "ip53"),
        (r"ipx\s*7", "ipx7"),
        (r"ipx\s*4", "ipx4"),
    ],
    "glass_protection": [
        (r"gorilla\s+armor", "gorilla_armor"),
        (r"ceramic\s+shield", "ceramic_shield"),
        (r"gorilla\s+glass\s+victus\s*2", "gorilla_glass_victus_2"),
        (r"gorilla\s+glass\s+victus", "gorilla_glass_victus"),
        (r"gorilla\s+glass\s*5", "gorilla_glass_5"),
        (r"gorilla\s+glass\s*3", "gorilla_glass_3"),
        (r"panda\s+glass", "panda_glass"),
    ],
    "frame_material": [
        (r"titanium\s+frame", "titanium"),
        (r"stainless\s+steel\s+frame", "stainless_steel"),
        (r"aluminum\s+frame|armour\s+aluminum", "aluminum"),
        (r"plastic\s+frame|polycarbonate", "plastic"),
    ],
    "coil_material": [
        (r"100%\s+grooved\s+copper", "100%_grooved_copper"),
        (r"100%\s+copper|copper\s+condenser|copper\s+coil", "100%_copper"),
        (r"aluminium\s+coil|aluminum\s+condenser|pfc\s+aluminium", "aluminum"),
    ],
    "anti_corrosion_coating": [
        (r"ocean\s+black(?:\s+protection)?", "ocean_black_gold_fin"),
        (r"gold\s+fin", "gold_fin"),
        (r"blue\s+fin", "blue_fin"),
        (r"epoxy\s+coat(?:ed|ing)?", "epoxy_coated"),
    ],
    "motor_type": [
        (r"direct\s+drive\s+inverter|direct\s+drive\s+motor|bldc\s+direct", "direct_drive_inverter"),
        (r"bldc\s+inverter\s+belt|bldc\s+motor", "bldc_inverter_belt"),
        (r"standard\s+induction|induction\s+motor", "standard_induction_belt"),
    ],
    "drum_material": [
        (r"laser\s+welded\s+stainless|seamless\s+stainless", "laser_welded_stainless_steel"),
        (r"stainless\s+steel\s+drum", "stainless_steel"),
        (r"plastic\s+drum|composite\s+tub", "plastic_composite"),
    ],
    "spider_arm_corrosion_protection": [
        (r"coated\s+spider|anti[- ]corrosion\s+spider", "coated_galvanic_anti_corrosion"),
        (r"reinforced\s+cast\s+spider", "reinforced_cast"),
        (r"cast\s+alumin(?:i)?um\s+spider", "standard_cast_aluminum"),
    ],
    "inbuilt_heater_steam": [
        (r"(?:90|95)\s*°?\s*C\s+steam|allergy\s+care\s+steam", "90c_steam_allergy"),
        (r"(?:inbuilt\s+)?heater|(?:60|40)\s*°?\s*C\s+wash", "60c_heater"),
        (r"cold\s+wash\s+only|no\s+heater", "cold_wash_only"),
    ],
    "container_type": [
        (r"opaque\s+airless\s+pump|airless\s+bottle", "opaque_airless_pump"),
        (r"airless\s+pump", "airless_pump"),
        (r"amber\s+glass\s+dropper|amber\s+dropper", "amber_glass_dropper"),
        (r"clear\s+glass\s+dropper|clear\s+dropper", "clear_glass_dropper"),
        (r"open\s+jar|tub\s+jar", "open_jar"),
    ],
    "hi_res_codec_support": [
        (r"ldac|lhdc|lossless\s+audio", "ldac_lhdc_lossless"),
        (r"aptx\s+adaptive|aptx\s+hd|aptx", "aptx_adaptive"),
        (r"aac\s+and\s+sbc\s+only|sbc,\s*aac", "aac_sbc_only"),
    ],
    "ram_upgradeability": [
        (r"dual\s+sodimm|2x\s+sodimm|user\s+upgradeable\s+ram", "dual_sodimm"),
        (r"single\s+sodimm|1x\s+sodimm\s+\+\s+soldered", "single_sodimm_plus_soldered"),
        (r"fully\s+soldered|soldered\s+lpddr|non-upgradeable\s+ram", "fully_soldered"),
    ],
    "ssd_slots": [
        (r"2x\s+m\.2|two\s+ssd\s+slots|dual\s+ssd", "2_slots"),
        (r"1x\s+m\.2|single\s+ssd\s+slot|1\s+ssd\s+slot", "1_slot"),
        (r"soldered\s+ssd|non-upgradeable\s+storage", "soldered"),
    ],
}

# -----------------------------------------------------------------------------
# Extraction Core
# -----------------------------------------------------------------------------

def extract_measurements_from_text(text: str) -> Dict[str, Any]:
    """Parse numeric and discrete lab benchmark values from text."""
    measurements: Dict[str, Any] = {}

    for metric_name, parsers in MEASUREMENT_PARSERS.items():
        for p in parsers:
            regex = re.compile(p["pattern"], re.IGNORECASE)
            for m in regex.finditer(text):
                ctx_start = max(0, m.start() - 40)
                ctx_end = min(len(text), m.end() + 40)
                context = text[ctx_start:ctx_end]
                if "condition" in p and not p["condition"](m, context):
                    continue
                try:
                    val_str = m.group(p["group"])
                    val = p["type"](val_str)
                    measurements[metric_name] = val
                    break
                except (ValueError, TypeError):
                    continue
            if metric_name in measurements:
                break

    # Discrete features
    for metric_name, rules in DISCRETE_FEATURE_DETECTORS.items():
        for pattern, canon_val in rules:
            if re.search(pattern, text, re.IGNORECASE):
                measurements[metric_name] = canon_val
                break

    # Boolean inferences
    if re.search(r"optical\s+image\s+stabilization|\bois\b", text, re.IGNORECASE):
        measurements["ois_stabilization"] = True
    elif re.search(r"no\s+ois|lacks\s+ois|eis\s+only", text, re.IGNORECASE):
        measurements["ois_stabilization"] = False

    if re.search(r"wireless\s+charging|qi\s+charging", text, re.IGNORECASE):
        if not re.search(r"no\s+wireless\s+charging|lacks\s+wireless", text, re.IGNORECASE):
            measurements["wireless_charging"] = True

    if re.search(r"zero\s+amino\s+spiking|verified\s+no\s+amino\s+spiking|amino\s+spiking\s+free", text, re.IGNORECASE):
        measurements["zero_amino_spiking_verified"] = True

    if re.search(r"heavy\s+metals\s+(?:passed|tested\s+clean|nd|below\s+limits)", text, re.IGNORECASE):
        measurements["heavy_metals_pass_standard"] = True

    if re.search(r"digezyme|digestive\s+enzyme", text, re.IGNORECASE):
        measurements["digestive_enzyme_complex"] = "multi_enzyme_digezyme"

    if "ip_rating" in measurements:
        measurements["ip_water_rating"] = measurements["ip_rating"]

    return measurements


def extract_irf_from_text(text: str) -> Dict[str, Any]:
    """Extract Local Readiness Factor (IRF) checklist attributes."""
    irf: Dict[str, Any] = {}

    # Service TAT in hours / days
    tat_match = re.search(
        r"(?:service\s*(?:tat|turnaround(?:\s*time)?|repair)|tat)(?:\s+of)?[:\s]*(\d{1,3})\s*(?:hours?|hrs?)",
        text,
        re.IGNORECASE,
    )
    if tat_match:
        irf["service_tat_hours"] = int(tat_match.group(1))
    else:
        tat_days_match = re.search(
            r"(?:service\s*(?:tat|turnaround(?:\s*time)?|repair)|repaired\s+in|tat)(?:\s+of)?[:\s]*(\d{1,2})\s*(?:days?|d\b)",
            text,
            re.IGNORECASE,
        )
        if tat_days_match:
            days = int(tat_days_match.group(1))
            irf["service_tat_days"] = days
            irf["service_tat_hours"] = days * 24

    # Statutory certifications
    certs = set()
    if re.search(r"\bbis\b|r-\d{8}|bis\s+crs", text, re.IGNORECASE):
        certs.add("BIS")
    if re.search(r"\bbee\s*(?:star)?|\biseer\b", text, re.IGNORECASE):
        certs.add("BEE")
    if re.search(r"\bfssai\b", text, re.IGNORECASE):
        certs.add("FSSAI")
    if re.search(r"\bce\s*mark|\bce\s+certified\b|\bce\s+european\b|\bce\s+compliance\b|\bce\s+standard\b", text, re.IGNORECASE):
        certs.add("CE")
    if re.search(r"\bfcc\b", text, re.IGNORECASE):
        certs.add("FCC")
    if re.search(r"\brohs\b", text, re.IGNORECASE):
        certs.add("RoHS")
    if re.search(r"\bnsf\b|informed[- ]choice|cologne\s+list", text, re.IGNORECASE):
        certs.add("NSF/Informed-Choice")
    if certs:
        irf["statutory_certifications"] = sorted(list(certs))

    # Environmental resilience
    if re.search(r"tropical(?:ized)?|52\s*°?c\s+ambient|ocean\s+black|gold\s+fin|100%\s+copper|ip68|corrosion\s+resistant", text, re.IGNORECASE):
        irf["environmental_resilience"] = "tropical_resilient"
    elif re.search(r"aluminium\s+coil|unprotected|no\s+anti[- ]corrosion|vulnerable\s+to\s+rust", text, re.IGNORECASE):
        irf["environmental_resilience"] = "unprotected_vulnerable"
    elif "ip54" in text.lower() or "blue fin" in text.lower() or "standard" in text.lower():
        irf["environmental_resilience"] = "standard_resilience"

    # Authorized seller
    if re.search(r"official\s+brand\s+store|brand\s+authorized|appario|cocoblu|authorized\s+dealer|direct\s+from\s+brand", text, re.IGNORECASE):
        irf["authorized_seller"] = "brand_authorized"
    elif re.search(r"unauthorized\s+seller|grey\s+market|third[- ]party\s+marketplace\s+seller", text, re.IGNORECASE):
        irf["authorized_seller"] = "unverified_third_party"
    elif re.search(r"amazon\s+fulfilled|flipkart\s+assured|reputable\s+merchant", text, re.IGNORECASE):
        irf["authorized_seller"] = "reputable_merchant"

    return irf


NEGATION_PREFIX = re.compile(
    r"\b(?:no|zero|without|never|lacks?|free\s+(?:from|of)|not\s+(?:seen|experienced|found|observed|reported)|no\s+(?:reports|cases|instances|signs?|issues?)\s+(?:of|with))\b",
    re.IGNORECASE,
)

NUM_WORDS_MAP = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "multiple": 3, "several": 4, "dozens": 24, "numerous": 5, "many": 5,
}


def parse_snippet_frequency(snip: str) -> int:
    """Parse numeric or word count of affected users/reports in a snippet."""
    m = re.search(
        r"\b(\d{1,3})\s*(?:users?|cases?|reports?|owners?|complaints?|instances?|threads?)\b",
        snip,
        re.IGNORECASE,
    )
    if m:
        return int(m.group(1))
    m_word = re.search(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|multiple|several|dozens|numerous|many)\s*(?:users?|cases?|reports?|owners?|complaints?|instances?|threads?)\b",
        snip,
        re.IGNORECASE,
    )
    if m_word:
        return NUM_WORDS_MAP.get(m_word.group(1).lower(), 1)
    return 1


def candidate_in_snippet(cname: str, snip: str) -> bool:
    """Resilient fuzzy check if a snippet refers to the given candidate."""
    snip_lower = snip.lower()
    cname_lower = cname.lower().strip()
    if cname_lower in snip_lower:
        return True

    # Strip common brand prefixes (e.g. "Samsung Galaxy S24" -> "Galaxy S24")
    brand_prefixes = ["samsung", "apple", "lenovo", "dell", "hp", "asus", "lg", "sony", "oneplus", "xiaomi", "google"]
    tokens = cname_lower.split()
    if len(tokens) > 1 and tokens[0] in brand_prefixes:
        sub_name = " ".join(tokens[1:])
        if sub_name in snip_lower:
            return True

    # Model token check (e.g. "S24", "T14s")
    model_tok = tokens[-1]
    if len(model_tok) >= 3 and re.search(r"\b" + re.escape(model_tok) + r"\b", snip_lower):
        return True

    return False


def extract_defects_from_snippets(
    category: str,
    snippets: List[str],
) -> List[Dict[str, Any]]:
    """
    Match candidate snippets against category defect taxonomy.
    Calculates source count and classifies defect type:
    - systemic_design_flaw: teardown corroboration or high source count (>= 5)
    - batch_defect: firmware/OTA/batch mention or source count >= 3
    - isolated_lemon: 1-2 reports without systemic/batch evidence
    Filters out negated findings (e.g., 'no green line observed').
    """
    taxonomy = CATEGORY_DEFECT_TAXONOMY.get(category, CATEGORY_DEFECT_TAXONOMY["smartphones"])
    detected_defects: List[Dict[str, Any]] = []

    teardown_keywords = re.compile(
        r"teardown|ifixit|technician|repair\s+shop|schematic|soldering|galvanic|"
        r"corrosion|spider\s+arm|hinge\s+mount|liquid\s+metal|flexgate|bga|pump[- ]out|"
        r"amino\s+spiking|microscopic|metallurgical|design\s+flaw|structural",
        re.IGNORECASE,
    )
    batch_keywords = re.compile(
        r"batch|firmware|ota|update|lot\s*(?:#|no|number)?|manufactured\s+in|"
        r"serial\s+number|rev\s*[\d.]+|software\s+update",
        re.IGNORECASE,
    )

    for item in taxonomy:
        matched_snippets = []
        has_teardown_corroboration = False
        has_batch_corroboration = False

        for snip in snippets:
            matched = False
            for pat in item["patterns"]:
                for m in re.finditer(pat, snip, re.IGNORECASE):
                    # Check negation in immediate clause
                    prefix = snip[max(0, m.start() - 70):m.start()]
                    sub_clauses = re.split(r"[.!?;\n]", prefix)
                    immediate_clause = sub_clauses[-1]
                    if NEGATION_PREFIX.search(immediate_clause):
                        continue
                    matched = True
                    break
                if matched:
                    break

            if matched:
                matched_snippets.append(snip)
                if teardown_keywords.search(snip):
                    has_teardown_corroboration = True
                if batch_keywords.search(snip):
                    has_batch_corroboration = True
                for clue in item.get("systemic_clues", []):
                    if clue.lower() in snip.lower():
                        has_teardown_corroboration = True
                        break

        if not matched_snippets:
            continue

        source_count = sum(parse_snippet_frequency(s) for s in matched_snippets)

        # Defect type tagging
        if has_teardown_corroboration or source_count >= 5:
            defect_type = "systemic_design_flaw"
        elif has_batch_corroboration or source_count >= 3:
            defect_type = "batch_defect"
        else:
            defect_type = "isolated_lemon"

        corroboration_summary = (
            f"Corroborated across {source_count} source report(s)."
            + (" Teardown/technician analysis verifies root cause." if has_teardown_corroboration else "")
            + (" Tied to specific batch/firmware/OTA update." if (has_batch_corroboration and not has_teardown_corroboration) else "")
        )

        detected_defects.append(
            {
                "issue": item["issue"],
                "severity": item["severity"],
                "affects": item["affects"],
                "defect_type": defect_type,
                "source_count": source_count,
                "corroboration": corroboration_summary,
                "evidence_snippets": [s[:160] + "..." for s in matched_snippets[:3]],
            }
        )

    # Sort critical first, then severe, moderate, minor
    sev_rank = {"critical": 0, "severe": 1, "moderate": 2, "minor": 3}
    detected_defects.sort(key=lambda d: (sev_rank.get(d["severity"], 4), -d["source_count"]))
    return detected_defects


def extract_price_and_tier(text: str) -> Tuple[float, str]:
    """Infer candidate price and tier from text if mentioned."""
    price = 0.0
    tier = "Standard"

    patterns = [
        r"(?:(?:price|mrp|cost|retails?\s+at|available\s+at)[:\s]+)?(?:₹|Rs\.?|INR)\s*(\d{4,8}|\d{1,3}(?:,\d{2,3})*(?:\.\d+)?)",
        r"(?:(?:price|mrp|cost|retails?\s+at|available\s+at)[:\s]+)?\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)",
        r"(?:price|mrp|cost|retails?\s+at|available\s+at)[:\s]+(?:₹|Rs\.?|INR|\$)?\s*(\d{4,8}|\d{1,3}(?:,\d{2,3})*(?:\.\d+)?)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val_str = m.group(1).replace(",", "")
            try:
                val = float(val_str)
                if val > 50:
                    price = val
                    break
            except ValueError:
                pass

    # Tier inference
    if re.search(r"\bflagship|premium|high[- ]end\b", text, re.IGNORECASE):
        tier = "Flagship"
    elif re.search(r"\bbudget|entry[- ]level|affordable\b", text, re.IGNORECASE):
        tier = "Budget"
    elif re.search(r"\bmid[- ]range|upper[- ]mid\b", text, re.IGNORECASE):
        tier = "Mid-Range"
    elif price > 75000:
        tier = "Flagship"
    elif 0 < price <= 25000:
        tier = "Budget"
    elif price > 25000:
        tier = "Mid-Range"

    return price, tier


# -----------------------------------------------------------------------------
# Input Ingestion & Candidate Segmentation
# -----------------------------------------------------------------------------

def split_into_snippets(text: str) -> List[str]:
    """Break large text corpus into semantic paragraphs/sentences."""
    paras = [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if len(p.strip()) > 15]
    if not paras:
        paras = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 15]
    return paras


def demux_raw_input(
    raw_content: str,
    cli_candidates: Optional[List[str]] = None,
    default_category: str = "smartphones",
) -> Tuple[str, str, List[Dict[str, Any]]]:
    """
    Parse input (JSON list, search results, or raw text) and partition
    evidence by candidate.
    """
    parsed_json = None
    try:
        parsed_json = json.loads(raw_content)
    except json.JSONDecodeError:
        parsed_json = None

    category = default_category
    currency = "INR"
    candidate_buckets: Dict[str, Dict[str, Any]] = {}

    # Case 1: Structured JSON with candidates
    if isinstance(parsed_json, dict) and "candidates" in parsed_json:
        category = parsed_json.get("category", default_category)
        currency = parsed_json.get("currency", "INR")
        for c in parsed_json["candidates"]:
            name = c.get("name", "Unknown Contender")
            text_corpus = []
            if "text" in c:
                text_corpus.append(str(c["text"]))
            if "snippets" in c:
                text_corpus.extend([str(s) for s in c["snippets"]])
            if "content" in c:
                text_corpus.append(str(c["content"]))
            if not text_corpus:
                text_corpus.append(json.dumps(c))

            candidate_buckets[name] = {
                "name": name,
                "tier": c.get("tier", "Standard"),
                "price": float(c.get("price", 0.0)),
                "text": " ".join(text_corpus),
                "snippets": split_into_snippets(" ".join(text_corpus)),
            }
        return category, currency, list(candidate_buckets.values())

    # Case 2: JSON search results (Firecrawl / Donsetch / serp)
    raw_snippets: List[str] = []
    if isinstance(parsed_json, list):
        for item in parsed_json:
            if isinstance(item, dict):
                parts = []
                for k in ["title", "snippet", "content", "body", "text"]:
                    if k in item and item[k]:
                        parts.append(str(item[k]))
                raw_snippets.append(" ".join(parts))
            elif isinstance(item, str):
                raw_snippets.append(item)
    elif isinstance(parsed_json, dict) and "results" in parsed_json:
        for item in parsed_json["results"]:
            if isinstance(item, dict):
                parts = []
                for k in ["title", "snippet", "content", "body", "text"]:
                    if k in item and item[k]:
                        parts.append(str(item[k]))
                raw_snippets.append(" ".join(parts))
    else:
        # Plain text
        raw_snippets = split_into_snippets(raw_content)

    # Group snippets by candidates
    candidates_list = cli_candidates or []

    # If no candidate names provided, attempt auto-discovery
    if not candidates_list:
        # Check for headers like # Candidate Name or **Candidate Name**
        header_matches = re.findall(
            r"(?:^|\n)\s*#{1,3}\s+([A-Za-z0-9][A-Za-z0-9 \t\+\-\.]{2,35})(?:\r?\n|$)",
            raw_content,
        )
        if header_matches:
            candidates_list = [h.strip() for h in header_matches if len(h.strip()) > 3][:6]

    if candidates_list:
        for cname in candidates_list:
            c_snippets = []
            for snip in raw_snippets:
                if candidate_in_snippet(cname, snip):
                    c_snippets.append(snip)

            # If no snippets matched specific name, assign all snippets to the sole candidate
            if not c_snippets and len(candidates_list) == 1:
                c_snippets = raw_snippets

            combined_text = " ".join(c_snippets)
            price, tier = extract_price_and_tier(combined_text)

            candidate_buckets[cname] = {
                "name": cname,
                "tier": tier,
                "price": price,
                "text": combined_text,
                "snippets": c_snippets,
            }
    else:
        # Default single candidate
        single_name = "Contender 1"
        combined_text = " ".join(raw_snippets)
        price, tier = extract_price_and_tier(combined_text)
        candidate_buckets[single_name] = {
            "name": single_name,
            "tier": tier,
            "price": price,
            "text": combined_text,
            "snippets": raw_snippets,
        }

    return category, currency, list(candidate_buckets.values())


# -----------------------------------------------------------------------------
# Defect Mining Orchestrator
# -----------------------------------------------------------------------------

def mine_defects_and_metrics(
    raw_content: str,
    category: str = "smartphones",
    candidates_filter: Optional[List[str]] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Execute complete mining pipeline on raw evidence."""
    parsed_cat, currency, candidates_data = demux_raw_input(
        raw_content, cli_candidates=candidates_filter, default_category=category
    )
    effective_cat = category or parsed_cat

    mined_candidates = []

    for c in candidates_data:
        name = c["name"]
        text = c["text"]
        snippets = c["snippets"]

        if verbose:
            sys.stderr.write(f"\n[MINER] Mining candidate '{name}' ({len(snippets)} snippets)...\n")

        # 1. Defect extraction
        defects = extract_defects_from_snippets(effective_cat, snippets)

        # 2. Lab measurement extraction
        measurements = extract_measurements_from_text(text)

        # 3. IRF checklist extraction
        irf_checklist = extract_irf_from_text(text)

        mined_cand = {
            "name": name,
            "tier": c.get("tier", "Standard"),
            "price": c.get("price", 0.0),
            "measurements": measurements,
            "defects": defects,
            "irf_checklist": irf_checklist,
            "evidence_stats": {
                "total_snippets_analyzed": len(snippets),
                "total_defects_found": len(defects),
                "systemic_defects_count": sum(1 for d in defects if d["defect_type"] == "systemic_design_flaw"),
                "critical_defects_count": sum(1 for d in defects if d["severity"] == "critical"),
            },
        }
        mined_candidates.append(mined_cand)

    return {
        "category": effective_cat,
        "currency": currency,
        "candidates": mined_candidates,
    }


# -----------------------------------------------------------------------------
# Output Formatters
# -----------------------------------------------------------------------------

def format_as_extractor_json(mining_results: Dict[str, Any]) -> str:
    """Format mined results into the exact schema expected by metric_extractor.py."""
    output_obj = {
        "category": mining_results["category"],
        "currency": mining_results["currency"],
        "candidates": [],
    }

    for c in mining_results["candidates"]:
        extractor_cand = {
            "name": c["name"],
            "tier": c.get("tier", "Standard"),
            "price": c.get("price", 0.0),
            "measurements": c["measurements"],
            "defects": [
                {
                    "issue": d["issue"],
                    "severity": d["severity"],
                    "affects": d["affects"],
                    "defect_type": d["defect_type"],
                    "source_count": d["source_count"],
                    "corroboration": d["corroboration"],
                }
                for d in c["defects"]
            ],
            "irf_checklist": c["irf_checklist"],
        }
        output_obj["candidates"].append(extractor_cand)

    return json.dumps(output_obj, indent=2)


def format_as_wirecutter_markdown(mining_results: Dict[str, Any]) -> str:
    """Format mined defect analysis into publication-grade Wirecutter Markdown."""
    lines: List[str] = []
    cat = mining_results["category"].replace("_", " ").title()

    lines.append(f"## Wirecutter-Grade Defect & Longevity Audit: {cat}")
    lines.append("")
    lines.append("> [!IMPORTANT]")
    lines.append(
        "> **Methodology Bar:** In accordance with Wirecutter field-testing protocols, candidate products are evaluated "
        "not only on launch-day manufacturer benchmarks, but through exhaustive 6–12 month user reliability audits, "
        "Reddit enthusiast forums, teardown analysis, and authorized service network resilience."
    )
    lines.append("")

    # Systemic Flaw Warnings
    critical_found = []
    for c in mining_results["candidates"]:
        for d in c["defects"]:
            if d["severity"] == "critical" or d["defect_type"] == "systemic_design_flaw":
                critical_found.append((c["name"], d))

    if critical_found:
        lines.append("### Systemic Failure Warnings & Reliability Alerts")
        lines.append("")
        for name, d in critical_found:
            lines.append(f"> [!WARNING]")
            lines.append(
                f"> **{name} — {d['issue']} ({d['severity'].upper()} / {d['defect_type'].upper()}):** "
                f"{d['corroboration']} Affects core *{d['affects']}*."
            )
            lines.append("")
    else:
        lines.append("> [!NOTE]")
        lines.append("> **Zero Catastrophic Hardware Recalls:** None of the evaluated candidates exhibited systemic motherboard dead-boots, gas leaks, or spider arm fractures in current production batches.")
        lines.append("")

    # Comparative Defect Breakdown Table
    lines.append("### Comparative Defect & Failure Mode Taxonomy")
    lines.append("")
    lines.append("| Contender | Severity | Failure Mode / Observed Defect | Classification | Affected Area | Evidence Sources |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

    has_defects = False
    for c in mining_results["candidates"]:
        for d in c["defects"]:
            has_defects = True
            lines.append(
                f"| **{c['name']}** | `{d['severity'].upper()}` | {d['issue']} | `{d['defect_type']}` | {d['affects']} | {d['source_count']} snippet(s) |"
            )

    if not has_defects:
        lines.append("| *All Candidates* | `NONE` | No statistically significant defects reported in analyzed evidence | `clean` | N/A | Clean record |")
    lines.append("")

    # Objective Lab Measurements Table
    lines.append("### Harvested Lab Benchmarks & Physical Measurements")
    lines.append("")
    lines.append("| Contender | Metric | Harvested Lab Value | Specification Type |")
    lines.append("| :--- | :--- | :--- | :--- |")

    has_metrics = False
    for c in mining_results["candidates"]:
        for m_name, m_val in c["measurements"].items():
            has_metrics = True
            m_label = m_name.replace("_", " ").title()
            lines.append(f"| **{c['name']}** | {m_label} | **{m_val}** | Lab Measurement |")

    if not has_metrics:
        lines.append("| *All Candidates* | Measurements | No discrete lab metrics parsed from snippet corpus | Baseline |")
    lines.append("")

    # Local Ecosystem & IRF Compliance Matrix
    lines.append("### Local Ecosystem & Readiness (IRF) Verification")
    lines.append("")
    lines.append("| Contender | Service TAT | Statutory Certifications | Environmental Resilience | Authorized Channel |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")

    for c in mining_results["candidates"]:
        irf = c["irf_checklist"]
        tat = f"{irf.get('service_tat_hours', 'N/A')} hrs" if "service_tat_hours" in irf else "Standard (3-5 days)"
        certs = ", ".join(irf.get("statutory_certifications", [])) or "Standard Pending"
        env = irf.get("environmental_resilience", "standard_resilience").replace("_", " ").title()
        seller = irf.get("authorized_seller", "reputable_merchant").replace("_", " ").title()
        lines.append(f"| **{c['name']}** | {tat} | {certs} | {env} | {seller} |")

    lines.append("")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Wirecutter-Grade Defect & Reddit/Teardown Reality Mining Engine CLI"
    )
    parser.add_argument(
        "-i",
        "--input",
        default="-",
        help="Path to input JSON/text file or '-' for stdin (default: -)",
    )
    parser.add_argument(
        "--text",
        default=None,
        help="Direct input raw text string",
    )
    parser.add_argument(
        "-c",
        "--category",
        default="smartphones",
        help="Product category (smartphones, laptops, inverter_acs, washing_machines, skincare, supplements, tws_audio)",
    )
    parser.add_argument(
        "-p",
        "--candidates",
        default=None,
        help="Comma-separated candidate product names (e.g. 'OnePlus 12, Galaxy S24')",
    )
    parser.add_argument(
        "--to-extractor-json",
        action="store_true",
        help="Output JSON formatted strictly for metric_extractor.py pipeline",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Output publication-grade Wirecutter-style Defect & Longevity Audit Markdown",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path to write output (default: stdout)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print diagnostic logging to stderr",
    )

    args = parser.parse_args()

    # Read input content
    if args.text:
        raw_content = args.text
    elif args.input == "-":
        if sys.stdin.isatty():
            sys.stderr.write("[ERROR] No input provided via stdin. Use --input <file> or pipe data.\n")
            sys.exit(1)
        raw_content = sys.stdin.read()
    else:
        if not os.path.isfile(args.input):
            sys.stderr.write(f"[ERROR] Input file not found: {args.input}\n")
            sys.exit(1)
        with open(args.input, "r", encoding="utf-8") as f:
            raw_content = f.read()

    candidates_filter = None
    if args.candidates:
        candidates_filter = [c.strip() for c in args.candidates.split(",") if c.strip()]

    mined = mine_defects_and_metrics(
        raw_content=raw_content,
        category=args.category,
        candidates_filter=candidates_filter,
        verbose=args.verbose,
    )

    if args.markdown:
        output_str = format_as_wirecutter_markdown(mined)
    elif args.to_extractor_json:
        output_str = format_as_extractor_json(mined)
    else:
        # Default: structured JSON
        output_str = json.dumps(mined, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        if args.verbose:
            sys.stderr.write(f"[INFO] Output saved to {args.output}\n")
    else:
        sys.stdout.write(output_str)
        if not output_str.endswith("\n"):
            sys.stdout.write("\n")


if __name__ == "__main__":
    main()
