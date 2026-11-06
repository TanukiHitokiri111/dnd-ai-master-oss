#!/usr/bin/env python3
"""
Полный тест-сьют системы смешанного наследия.
Гонять до нуля багов.
"""
import importlib.util, sys, json, random
from pathlib import Path
from collections import defaultdict

BACKEND = Path(__file__).resolve().parents[1]
SRD_PATH = BACKEND / "app" / "knowledge" / "srd_rules.py"
HERITAGE_PATH = BACKEND / "app" / "services" / "heritage_roller.py"

FAIL = 0
PASS = 0

def check(condition, msg):
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        print(f"  ❌ {msg}")

# ── 1. Load srd_rules ──
spec = importlib.util.spec_from_file_location('srd', str(SRD_PATH))
srd = importlib.util.module_from_spec(spec)
sys.modules['srd'] = srd
spec.loader.exec_module(srd)

mc = srd.MIXED_HERITAGE_CONFIG
vt = srd.MIXED_VISUAL_TRAITS
cr = srd.COMPAT_RULES
rt = srd.RACIAL_TRAITS

KNOWN = set(rt.keys())

print("=" * 60)
print("ТЕСТЫ СМЕШАННОГО НАСЛЕДИЯ")
print("=" * 60)

# ── 2. Coverage ──
print("\n── COVERAGE ──")
for name in sorted(KNOWN):
    check(name in mc, f"{name} missing in MIXED_HERITAGE_CONFIG")
    check(name in vt, f"{name} missing in MIXED_VISUAL_TRAITS")
    check(name in cr, f"{name} missing in COMPAT_RULES")

extra_mc = set(mc) - KNOWN
check(not extra_mc, f"Extra in MIXED_HERITAGE_CONFIG: {extra_mc}")
extra_vt = set(vt) - KNOWN
check(not extra_vt, f"Extra in MIXED_VISUAL_TRAITS: {extra_vt}")
extra_cr = set(cr) - KNOWN
check(not extra_cr, f"Extra in COMPAT_RULES: {extra_cr}")

# ── 3. MIXED_HERITAGE_CONFIG structure ──
print("\n── MIXED_HERITAGE_CONFIG STRUCTURE ──")
REQUIRED_KEYS = {"size_category", "speed", "languages", "physical_traits", "magical_traits", "guaranteed"}
for name, cfg in mc.items():
    for k in REQUIRED_KEYS:
        check(k in cfg, f"{name}: missing key '{k}'")
    check(isinstance(cfg.get("speed"), int) and 20 <= cfg["speed"] <= 50,
          f"{name}: bad speed={cfg.get('speed')}")
    check(cfg.get("size_category") in ("small", "medium"),
          f"{name}: bad size={cfg.get('size_category')}")
    check(isinstance(cfg.get("languages"), list), f"{name}: languages not a list")
    check(isinstance(cfg.get("guaranteed"), list), f"{name}: guaranteed not a list")
    # physical_traits
    for tname, tdata in cfg.get("physical_traits", {}).items():
        check(isinstance(tdata, dict), f"{name}.physical.{tname}: not a dict")
        check("chance" in tdata, f"{name}.physical.{tname}: missing 'chance'")
        check("desc" in tdata, f"{name}.physical.{tname}: missing 'desc'")
        check(isinstance(tdata.get("chance"), (int, float)), f"{name}.physical.{tname}: chance not numeric")
        check(5 <= tdata.get("chance", 0) <= 90, f"{name}.physical.{tname}: chance out of range={tdata.get('chance')}")
    # magical_traits
    for tname, tdata in cfg.get("magical_traits", {}).items():
        check(isinstance(tdata, dict), f"{name}.magical.{tname}: not a dict")
        check("chance" in tdata, f"{name}.magical.{tname}: missing 'chance'")
        check("desc" in tdata, f"{name}.magical.{tname}: missing 'desc'")

# ── 4. MIXED_VISUAL_TRAITS structure ──
print("\n── MIXED_VISUAL_TRAITS STRUCTURE ──")
for name, vtraits in vt.items():
    check(isinstance(vtraits, list), f"{name}: visual traits not a list")
    for v in vtraits:
        check(isinstance(v, dict), f"{name}: visual trait not a dict")
        check("name" in v, f"{name}: visual trait missing name")
        check("chance_multiplier" in v, f"{name}: visual trait missing chance_multiplier")
        check("desc" in v, f"{name}: visual trait missing desc")

# ── 5. COMPAT_RULES consistency ──
print("\n── COMPAT_RULES CONSISTENCY ──")

# 5a. Symmetry: if A lists B, B must list A
for race_a, rule_a in cr.items():
    for race_b in rule_a.get("compatible_with", []):
        rule_b = cr.get(race_b, {})
        check(race_a in rule_b.get("compatible_with", []),
              f"Asymmetry: {race_a}→{race_b} but not {race_b}→{race_a}")

# 5b. No self-reference
for race, rule in cr.items():
    check(race not in rule.get("compatible_with", []),
          f"Self-reference: {race} in its own compatible_with")

# 5c. Blocked races
for race in ["Кованый", "Возрождённый"]:
    rule = cr.get(race, {})
    check(not rule.get("can_mix", True), f"{race} should be blocked")
    check(rule.get("compatible_with") == [], f"{race} should have empty compatible_with, got {rule.get('compatible_with')}")

# 5d. Universal races (Чейнджлинг, Дампир) can mix with almost everyone
for race in ["Чейнджлинг", "Дампир"]:
    rule = cr.get(race, {})
    check(rule.get("can_mix", False), f"{race} should be universal (can_mix=True)")
    compat = rule.get("compatible_with", [])
    check("Кованый" not in compat, f"{race} should NOT include Кованый")
    check("Возрождённый" not in compat, f"{race} should NOT include Возрождённый")
    check(len(compat) >= 40, f"{race} should have 40+ compat, has {len(compat)}")

# 5e. Гуманоиды совместимы с гуманоидами
humanoids = [r for r, rule in cr.items() if rule.get("group") == "HUMANOID_CLASSIC"]
for h in humanoids:
    for h2 in humanoids:
        if h == h2: continue
        check(h2 in cr[h]["compatible_with"], f"Humanoid {h} should be compat with humanoid {h2}")

# 5f. Рептилии совместимы друг с другом
reptiles = [r for r, rule in cr.items() if rule.get("group") == "REPTILIAN"]
for r1 in reptiles:
    for r2 in reptiles:
        if r1 == r2: continue
        check(r2 in cr[r1]["compatible_with"], f"Reptilian {r1} should be compat with reptilian {r2}")

# 5g. Феи совместимы друг с другом
fey = [r for r, rule in cr.items() if rule.get("group") == "FEY"]
for f1 in fey:
    for f2 in fey:
        if f1 == f2: continue
        check(f2 in cr[f1]["compatible_with"], f"Fey {f1} should be compat with fey {f2}")

# 5h. Every race with can_mix=True has at least one compatible
for race, rule in cr.items():
    if rule.get("can_mix", False):
        check(len(rule.get("compatible_with", [])) > 0,
              f"{race} can_mix=True but compatible_with is empty")

# ── 6. Heritage Roller logic ──
print("\n── HERITAGE ROLLER ──")
# Execute the heritage roller code in our namespace (it imports from app.knowledge.srd_rules
# but we already have srd loaded)
import types, copy
# Create a fake app.knowledge module structure
# Create fake app package structure so from app.knowledge.srd_rules import works
app = types.ModuleType('app')
app_knowledge = types.ModuleType('app.knowledge')
app_knowledge.__path__ = []  # marks it as a package
app_knowledge.srd_rules = srd
app_knowledge.__dict__.update({
    'MIXED_HERITAGE_CONFIG': srd.MIXED_HERITAGE_CONFIG,
    'MIXED_VISUAL_TRAITS': srd.MIXED_VISUAL_TRAITS,
    'COMPAT_RULES': srd.COMPAT_RULES,
    'MIXED_TRAIT_CATEGORIES': getattr(srd, 'MIXED_TRAIT_CATEGORIES', {'visual': {'default_chance': 50}}),
    'MIXED_LANGUAGE_THRESHOLD': getattr(srd, 'MIXED_LANGUAGE_THRESHOLD', 30),
    'RACIAL_SUBRACES': getattr(srd, 'RACIAL_SUBRACES', {}),
})
app.knowledge = app_knowledge
app.services = types.ModuleType('app.services')
sys.modules['app'] = app
sys.modules['app.knowledge'] = app_knowledge
sys.modules['app.knowledge.srd_rules'] = srd
sys.modules['app.services'] = app.services

# Now execute heritage_roller
hr_code = open(HERITAGE_PATH).read()
hr_exec = {}
try:
    exec(hr_code, hr_exec)
    roll = hr_exec.get('roll_mixed_heritage')
    check_compat = hr_exec.get('check_compatibility')
    get_compat = hr_exec.get('get_compatible_races')
except Exception as e:
    print(f"  ❌ Could not import heritage_roller: {e}")
    roll = lambda *a, **kw: {}  # dummy
    check_compat = lambda *a: []
    get_compat = lambda *a: []

if not roll:
    print("  ❌ Could not load roll_mixed_heritage from heritage_roller.py")
    roll = lambda *a, **kw: {}  # dummy

# 6a. Valid rolls for N races
test_combos = [
    ({"Человек": 50, "Эльф": 50}, "Standard human-elf"),
    ({"Человек": 100}, "100% single race"),
    ({"Человек": 40, "Эльф": 30, "Дварф": 30}, "Three-way mix"),
    ({"Чейнджлинг": 50, "Драконорождённый": 50}, "Universal + reptilian"),
    ({"Дампир": 50, "Тифлинг": 50}, "Universal + planetouched"),
    ({"Гоблин": 70, "Орк": 30}, "Goblinoid + orc"),
    ({"Драконорождённый": 50, "Кобольд": 50}, "Reptilian-reptilian"),
    ({"Фэйри": 50, "Сатир": 50}, "Fey-fey"),
    ({"Кентавр": 60, "Человек": 40}, "Fey-humanoid"),
]
for combo, desc in test_combos:
    try:
        result = roll(combo, seed=42)
        check(isinstance(result, dict), f"Roll {desc}: result is not dict")
        check("dominant_species" in result, f"Roll {desc}: missing dominant_species")
        check("physical_traits" in result, f"Roll {desc}: missing physical_traits")
        check("magical_traits" in result, f"Roll {desc}: missing magical_traits")
        check("visual_traits" in result, f"Roll {desc}: missing visual_traits")
        check("speed" in result, f"Roll {desc}: missing speed")
        check("size_category" in result, f"Roll {desc}: missing size_category")
        check("languages" in result, f"Roll {desc}: missing languages")
        check("Общий" in result.get("languages", []), f"Roll {desc}: missing Общий language")
        check(result["speed"] % 5 == 0, f"Roll {desc}: speed not multiple of 5")
        check(20 <= result["speed"] <= 40, f"Roll {desc}: speed out of range={result['speed']}")
        check(result["size_category"] in ("small", "medium"), f"Roll {desc}: bad size")
        # dominant must be one of the input races
        check(result["dominant_species"] in combo, f"Roll {desc}: dominant species not in input")
        # percentages should sum to 100
        check(sum(result["species_percentages"].values()) == 100,
              f"Roll {desc}: percentages sum to {sum(result['species_percentages'].values())}")
    except Exception as e:
        check(False, f"Roll {desc}: exception: {e}")

# 6b. Reject blocked races
blocked_combos = [
    ({"Кованый": 100}, "Construct alone"),
    ({"Возрождённый": 100}, "Undead alone"),
    ({"Кованый": 50, "Человек": 50}, "Construct + human"),
    ({"Человек": 50, "Возрождённый": 50}, "Human + undead"),
]
for combo, desc in blocked_combos:
    try:
        roll(combo, seed=42)
        check(False, f"Roll {desc}: should have raised ValueError")
    except ValueError as e:
        check(True, f"Roll {desc}: correctly rejected")
    except Exception as e:
        check(False, f"Roll {desc}: wrong exception {type(e).__name__}: {e}")

# 6c. Reject unknown races
try:
    roll({"НеизвестнаяРаса": 100}, seed=42)
    check(False, "Unknown race should raise ValueError")
except ValueError:
    check(True, "Unknown race correctly rejected")

# 6d. check_compatibility function
check(check_compat(["Человек", "Эльф"]) == [], "check_compat human-elf should be empty")
check(len(check_compat(["Кованый"])) > 0, "check_compat construct should return errors")
check(len(check_compat(["Человек", "Кованый"])) > 0, "check_compat human+construct should return errors")

# 6e. get_compatible_races
check(len(get_compat("Человек")) >= 40, f"get_compat(Человек) should be 40+, got {len(get_compat('Человек'))}")
check(get_compat("Кованый") == [], f"get_compat(Кованый) should be empty, got {get_compat('Кованый')}")

# 6f. Determinism (local RNG)
r1 = roll({"Человек": 50, "Эльф": 50}, seed=123)
r2 = roll({"Человек": 50, "Эльф": 50}, seed=123)
check(r1 == r2, "Same seed should produce identical results")
# Different seeds may or may not differ — probabilistic

# ── 7. API tests ──
print("\n── API TESTS ──")
import subprocess

def api(path, method="GET", data=None):
    url = f"http://127.0.0.1:8000{path}"
    opts = ["-s", "-o", "/dev/null", "-w", "%{http_code}"]
    if method == "POST":
        opts.extend(["-X", "POST", "-H", "Content-Type: application/json"])
        if data:
            opts.extend(["-d", json.dumps(data)])
    result = subprocess.run(["curl"] + opts + [url], capture_output=True, text=True, timeout=10)
    return result.stdout.strip()

def api_json(path, method="GET", data=None):
    url = f"http://127.0.0.1:8000{path}"
    opts = ["-s"]
    if method == "POST":
        opts.extend(["-X", "POST", "-H", "Content-Type: application/json"])
        if data:
            opts.extend(["-d", json.dumps(data)])
    result = subprocess.run(["curl"] + opts + [url], capture_output=True, text=True, timeout=10)
    return json.loads(result.stdout)

# 7a. Health
check(api("/health") == "200", "API /health not 200")

# 7b. Config endpoint
cfg = api_json("/api/v1/characters/mixed-heritage/config")
check("species" in cfg, "Config: missing 'species' key")
check(len(cfg["species"]) == 47, f"Config: expected 47 species (excl. Смешанная), got {len(cfg['species'])}")
for s in cfg["species"]:
    check("name" in s, f"Config species missing name")
    check("can_mix" in s, f"Config species {s.get('name')} missing can_mix")
    check("group" in s, f"Config species {s.get('name')} missing group")
kovany = [s for s in cfg["species"] if s["name"] == "Кованый"]
check(len(kovany) == 1 and kovany[0]["can_mix"] is False, "Кованый should be can_mix=False in config")

# 7c. Compatible endpoint
compat_human = api_json("/api/v1/characters/mixed-heritage/compatible/Человек")
check(compat_human["can_mix"] is True, "Человек can_mix should be True")
check(len(compat_human["compatible_with"]) >= 40, f"Человек compat should be 40+")

compat_warforged = api_json("/api/v1/characters/mixed-heritage/compatible/Кованый")
check(compat_warforged["can_mix"] is False, "Кованый can_mix should be False")
check(compat_warforged["compatible_with"] == [], "Кованый compat should be empty")

compat_changeling = api_json("/api/v1/characters/mixed-heritage/compatible/Чейнджлинг")
check(compat_changeling["can_mix"] is True, "Чейнджлинг can_mix should be True")
check(len(compat_changeling["compatible_with"]) >= 40, f"Чейнджлинг compat should be 40+")

# 7d. Check endpoint
chk1 = api_json("/api/v1/characters/mixed-heritage/check", "POST",
                {"species_percentages": {"Человек": 50, "Эльф": 50}})
check(chk1["compatible"] is True, "Check human-elf should be compatible")
check(chk1["errors"] == [], f"Check human-elf should have no errors: {chk1['errors']}")

chk2 = api_json("/api/v1/characters/mixed-heritage/check", "POST",
                {"species_percentages": {"Кованый": 100}})
check(chk2["compatible"] is False, "Check construct should be incompatible")
check(len(chk2["errors"]) > 0, "Check construct should have errors")

chk3 = api_json("/api/v1/characters/mixed-heritage/check", "POST",
                {"species_percentages": {"Человек": 50, "Грунг": 50}})
check(chk3["compatible"] is True, f"Check human-grung should be compatible: {chk3['errors']}")

# 7f: Universal + CONSTRUCT must be blocked
chk4 = api_json("/api/v1/characters/mixed-heritage/check", "POST",
                {"species_percentages": {"Чейнджлинг": 50, "Кованый": 50}})
check(chk4["compatible"] is False, f"Changeling+Construct should be incompatible: {chk4}")
check(len(chk4["errors"]) > 0, "Changeling+Construct should have errors")

chk5 = api_json("/api/v1/characters/mixed-heritage/check", "POST",
                {"species_percentages": {"Дампир": 50, "Возрождённый": 50}})
check(chk5["compatible"] is False, f"Dhampir+Undead should be incompatible: {chk5}")

# 7e. Roll endpoint
roll_resp = api_json("/api/v1/characters/mixed-heritage/roll", "POST",
                     {"species_percentages": {"Человек": 50, "Гоблин": 50}, "seed": 42})
check("dominant_species" in roll_resp, "Roll API: missing dominant_species")
check(roll_resp["dominant_species"] in ("Человек", "Гоблин"), "Roll API: bad dominant")
check(sum(roll_resp["species_percentages"].values()) == 100, "Roll API: bad total")

# ── 8. Edge cases ──
print("\n── EDGE CASES ──")

# 8a. Empty percentages
try:
    roll({}, seed=42)
    check(False, "Empty dict should raise")
except ValueError:
    check(True, "Empty dict correctly rejected")

# 8b. Sum not ~100 (должно падать — фронт всегда шлёт 100, валидация обязательна)
try:
    roll({"Человек": 50, "Эльф": 30}, seed=42)
    check(False, "Sum < 95 should raise ValueError")
except ValueError as e:
    check("95" in str(e) or "100%" in str(e), f"Expected sum validation, got: {e}")

# 8c. Negative/zero percentages
try:
    roll({"Человек": -10}, seed=42)
    check(False, "Negative should fail")
except ValueError:
    check(True, "Negative correctly rejected")
try:
    roll({"Человек": 0}, seed=42)
    check(False, "Zero should fail")
except ValueError:
    check(True, "Zero correctly rejected (total <= 0)")
try:
    roll({"Человек": 100, "Эльф": 0}, seed=42)
    check(False, "Zero elf should fail")
except ValueError:
    check(True, "Zero elf rejected (pct <= 0)")

# 8d. Все новые расы имеют хотя бы один трейт
for name in KNOWN:
    cfg = mc[name]
    total_traits = len(cfg.get("physical_traits", {})) + len(cfg.get("magical_traits", {}))
    if name != "Смешанная":  # эта специальная
        check(total_traits > 0, f"{name}: no traits at all ({total_traits})")

# ── SUMMARY ──
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"PASS: {PASS}/{total} ({100*PASS/total:.0f}%)")
print(f"FAIL: {FAIL}/{total}")
if FAIL == 0:
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ — НОЛЬ БАГОВ")
else:
    print(f"❌ {FAIL} БАГОВ — НУЖНО ЧИНИТЬ")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
