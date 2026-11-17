# ==============================================================================
# SkillXray -> Hugging Face: export the data the Space needs.        PASTE THIS INTO A NOTEBOOK CELL AND RUN IT ONCE.
# ==============================================================================
# Run it in the Colab session of the current SkillXray notebook, AFTER:
#   - the notebook has run through section 17 (PROFILE_OF, NS_SPANS, NS_WIN, BG_EVID and role_phrases exist), and
#   - freeze_profiles() has written a release_*.parquet you are happy with (17c).  Without a release the Space falls back to the
#     static profiles from section 10, which still works.
# It (1) makes sure every requirement label has z-score statistics, (2) saves the posting phrases the report shows,
# (3) copies every file the Space reads into <BASE_DIR>/space_bundle/ with the same folder layout, and (4) zips it.
# Unzip skillxray_data.zip INTO the Space folder (next to app.py) and push.
import os, json, glob, shutil, zipfile
import pandas as pd

BUNDLE = os.path.join(BASE_DIR, 'space_bundle')
ZIP_PATH = os.path.join(BASE_DIR, 'skillxray_data.zip')

# ---- 1. z-score statistics for every requirement the app can show (static profiles + the latest frozen release)
labels = set(l for p in PROFILE_OF.values() for l in p['esco_label'].astype(str))
rel_files = sorted(glob.glob(os.path.join(LIVE_DIR, 'release_*.parquet')))
if rel_files:
    labels |= set(pd.read_parquet(rel_files[-1])['esco_label'].astype(str))
else:
    print("[!] no release_*.parquet in", LIVE_DIR, "- the Space will use the static profiles. Run freeze_profiles() to ship live ones.")
miss_s = sorted(l for l in labels if l not in NS_SPANS.s)
miss_w = sorted(l for l in labels if l not in NS_WIN.s)
if miss_s or miss_w:
    if 'BG_EVID' in globals():
        NS_SPANS.E = [e[0] for e in BG_EVID if e[0].shape[0] > 0]; NS_SPANS.ensure(miss_s)
        NS_WIN.E = [e[1] for e in BG_EVID if e[1].shape[0] > 0];   NS_WIN.ensure(miss_w)
        print(f"computed statistics for {len(miss_s)} + {len(miss_w)} new requirement labels")
    else:
        print(f"[!] {len(miss_s)} labels have no statistics and BG_EVID is not in memory (re-run cell 16c first). "
              "The Space will use default values for them and say so in the report.")
NS_SPANS.save(os.path.join(RESULTS_DIR, 'matching_v2_stats_spans.json'))
NS_WIN.save(os.path.join(RESULTS_DIR, 'matching_v2_stats_windows.json'))

# ---- 2. the wording postings use for each static requirement (shown next to a gap)
try:
    phrases = {r: role_phrases(r) for r in PROFILE_OF if r in role_post_ids}
    json.dump(phrases, open(os.path.join(RESULTS_DIR, 'role_phrases.json'), 'w'))
except Exception as e:
    print("[!] role_phrases.json skipped:", type(e).__name__, e)

# ---- 3. copy everything the Space reads
linker_config_path = os.path.join(BASE_DIR, 'models/linker/linker_config.json')
linker_config = json.load(open(linker_config_path)) if os.path.exists(linker_config_path) else {}
sbert_model = linker_config.get('sbert_model', 'all-MiniLM-L6-v2')
embedding_name = ('esco_term_embeddings.npy' if sbert_model == 'all-MiniLM-L6-v2'
                  else f"esco_term_embeddings_{sbert_model.replace('/', '_')}.npy")
FILES = [
    'data/esco/skills_en.csv', 'data/esco/extra_terms.txt', 'data/esco/link_overrides.csv',
    'data/esco/skillSkillRelations_en.csv', 'data/esco/broaderRelationsSkillPillar_en.csv',
    os.path.join('models/sbert', embedding_name), 'models/sbert/esco_hubness_k10.npy',    # the hubness file only exists if you used it
    'models/linker/linker_config.json',
    'results/extraction_config.json', 'results/matching_v2_config.json',
    'results/matching_v2_stats_spans.json', 'results/matching_v2_stats_windows.json',
    'results/requirement_blocklist.csv', 'results/role_phrases.json',
    'data/processed/extracted/role_profiles.parquet',
]
if rel_files:
    FILES += [os.path.relpath(rel_files[-1], BASE_DIR), os.path.relpath(rel_files[-1], BASE_DIR).replace('.parquet', '.json')]
OPTIONAL = ('esco_hubness', 'release_', 'skillSkillRelations', 'broaderRelations')
shutil.rmtree(BUNDLE, ignore_errors=True)
copied, missing = [], []
for rel in FILES:
    src = os.path.join(BASE_DIR, rel)
    if os.path.exists(src):
        dst = os.path.join(BUNDLE, rel); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst)
        copied.append((rel, os.path.getsize(src) / 1e6))
    else:
        missing.append(rel)

# ---- 4. zip
with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
    for rel, _ in copied:
        z.write(os.path.join(BUNDLE, rel), rel)
print(f"\ncopied {len(copied)} files ({sum(s for _, s in copied):.1f} MB):")
for rel, mb in copied:
    print(f"  {mb:8.1f} MB  {rel}")
bad = [m for m in missing if not any(o in m for o in OPTIONAL)]
if missing:
    print("\nnot found:", *missing, sep="\n  ")
if bad:
    print("\n[!] these are REQUIRED, the Space will not start without them:", *bad, sep="\n  ")
print("\nzip:", ZIP_PATH, "\n(Colab: from google.colab import files; files.download(ZIP_PATH))")
