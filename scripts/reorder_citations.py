#!/usr/bin/env python3
"""
Reorganize citations in editableAgente.docx to sequential IEEE order.
Run-aware: replaces citation text within existing runs, preserving formatting.
Only merges runs when a citation spans multiple runs.
"""
from lxml import etree
from zipfile import ZipFile, ZIP_DEFLATED
from copy import deepcopy
import re, shutil, os

DOCX = "/home/bastian/Documents/code/vermicompost-iot/docs/editableAgente.docx"
BACKUP = DOCX + ".backup"
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ns = '{' + W + '}'

if not os.path.exists(BACKUP):
    shutil.copy2(DOCX, BACKUP)

with ZipFile(DOCX) as z:
    doc_xml = z.read('word/document.xml')

root = etree.fromstring(doc_xml)
body = root.find(f'./{ns}body')
paras = body.findall(f'.//{ns}p')

# ── Run-aware text helpers ──

def get_run_texts(p):
    """(run_elem, combined_text) for each run with text."""
    return [(r, ''.join(t.text or '' for t in r.findall(f'.//{ns}t')))
            for r in p.findall(f'./{ns}r')]

def find_span(run_texts, needle):
    """Find needle span across runs. [(idx, start, end)] or None."""
    combined = ''.join(t for _, t in run_texts)
    pos = combined.find(needle)
    if pos < 0:
        return None
    end = pos + len(needle)
    cum = 0
    out = []
    for i, (_, txt) in enumerate(run_texts):
        run_end = cum + len(txt)
        if pos < run_end and cum < end:
            out.append((i, max(0, pos - cum), min(len(txt), end - cum)))
        cum = run_end
    return out

def replace_in_para(p, old_str, new_str):
    """Replace old_str→new_str, preserving runs when possible, merging only when needed."""
    run_texts = get_run_texts(p)
    combined = ''.join(t for _, t in run_texts)
    if old_str not in combined:
        return False
    spans = find_span(run_texts, old_str)
    if not spans:
        return False
    if len(spans) == 1:
        i, start, end = spans[0]
        r, _ = run_texts[i]
        for t in r.findall(f'.//{ns}t'):
            if t.text is not None:
                t.text = t.text[:start] + new_str + t.text[end:]
                return True
        return False
    # Multi-run: merge affected runs into first, keep formatting of first
    first = spans[0][0]
    last = spans[-1][0]
    affected = ''.join(t for i, (_, t) in enumerate(run_texts) if first <= i <= last)
    new_affected = affected.replace(old_str, new_str, 1)
    r0, _ = run_texts[first]
    t0 = r0.find(f'./{ns}t')
    if t0 is not None:
        t0.text = new_affected
    for j in range(first + 1, last + 1):
        rj, _ = run_texts[j]
        for tj in rj.findall(f'.//{ns}t'):
            tj.text = ''
    return True

def para_text(p):
    return ''.join(t.text or '' for t in p.findall(f'.//{ns}t'))

# ══════════════════════════════════════════════════════════════
# PHASE 1: Specific text modifications (run-aware)
# ══════════════════════════════════════════════════════════════

# 1A: ISO 9241-110 at para 352
t_old = 'cumpliendo con los estándares internacionales de experiencia de usuario (UX) exigidos'
t_new = 'cumpliendo con los estándares internacionales de experiencia de usuario (UX) e interacción humano-sistema [__ISO__] exigidos'
if replace_in_para(paras[352], t_old, t_new):
    print(f"[1A] ISO 9241-110 placeholder at para 352 ✓")

# 1B: ISO 9241-110 at para 673
t_old = 'directivas de ergonomía de interfaces de software, permitiendo'
t_new = 'directivas de ergonomía de interfaces de software e interacción humano-sistema [__ISO__], permitiendo'
if replace_in_para(paras[673], t_old, t_new):
    print(f"[1B] ISO 9241-110 placeholder at para 673 ✓")

# 1C: ANSI/ISA-101.01 at para 407
if replace_in_para(paras[407], 'bajo el estándar ANSI/ISA-101.01,', 'bajo el estándar ANSI/ISA-101.01 [__ANSI__],'):
    print(f"[1C] ANSI/ISA-101.01 placeholder at para 407 ✓")

# 1D: Fix Node-RED at para 448
if replace_in_para(paras[448], 'como gateway o capa de automatización [24].', 'como gateway o capa de automatización [__NODE__].'):
    print(f"[1D] Node-RED placeholder at para 448 ✓")

# 1E: Disambiguate duplicate [23]
# Specific paragraphs first
for pi, suffix in [(453, '23-API'), (725, '23-NGINX'), (731, '23-NGINX')]:
    t = para_text(paras[pi])
    if '[23]' in t:
        replace_in_para(paras[pi], '[23]', f'[{suffix}]')
# All remaining [23] in body → Ubidots API context
for i in range(0, 756):
    t = para_text(paras[i])
    if '[23]' in t:
        replace_in_para(paras[i], '[23]', '[23-API]')
print(f"[1E] Duplicate [23] disambiguated ✓")

# ══════════════════════════════════════════════════════════════
# PHASE 2: Reorder REFERENCIAS (BEFORE global renumbering)
# ══════════════════════════════════════════════════════════════

new_order = [
    (1,  757,  '1'),     (2,  768,  '12'),    (3,  758,  '2'),
    (4,  760,  '4'),     (5,  762,  '6'),     (6,  763,  '7'),
    (7,  761,  '5'),     (8,  764,  '8'),     (9,  759,  '3'),
    (10, 766,  '10'),    (11, 765,  '9'),     (12, 784,  '27'),
    (13, 767,  '11'),    (14, 774,  '18'),    (15, 770,  '14'),
    (16, 771,  '15'),    (17, 772,  '16'),    (18, 769,  '13'),
    (19, 773,  '17'),    (20, 775,  '19'),    (21, 776,  '20'),
    (22, 777,  '21'),    (23, 778,  '22'),    (24, 779,  '23'),
    (25, 780,  '23'),    (26, 781,  '24'),    (27, 782,  '25'),
    (28, 783,  '26'),
]

print(f"\n[Phase 2] Reordering references…")

reordered = []
for new_n, old_idx, old_n_str in new_order:
    p = deepcopy(paras[old_idx])
    # Replace header [old_n] with [new_n], first occurrence only
    combined = para_text(p)
    old_hdr = f'[{old_n_str}]'
    new_hdr = f'[{new_n}]'
    if combined.startswith(old_hdr):
        new_combined = new_hdr + combined[len(old_hdr):]
    else:
        new_combined = combined.replace(old_hdr, new_hdr, 1)
    if new_combined != combined:
        # Only change the header; preserve runs
        # Find and replace the FIRST occurrence of old_hdr
        replace_in_para(p, old_hdr, new_hdr)
    reordered.append(p)

# Replace reference paragraphs in tree
for i, new_p in enumerate(reordered):
    idx = 757 + i
    old_p = paras[idx]
    for child in list(old_p):
        old_p.remove(child)
    for child in new_p:
        old_p.append(child)

print(f"  Reordered {len(reordered)} entries ✓")

# ══════════════════════════════════════════════════════════════
# PHASE 3: Global citation renumbering (single-pass regex, run-aware)
# ══════════════════════════════════════════════════════════════

MAPPING = {
    '1': '1',       '2': '3',       '3': '9',       '4': '4',
    '5': '7',       '6': '5',       '7': '6',       '8': '8',
    '9': '11',      '10': '10',     '11': '13',     '12': '2',
    '13': '18',     '14': '15',     '15': '16',     '16': '17',
    '17': '19',     '18': '14',     '19': '20',     '20': '21',
    '21': '22',     '22': '23',     '23-API': '24', '23-NGINX': '25',
    '24': '26',     '25': '27',     '26': '28',     '27': '12',
}

# Order mappings by old_n descending length to avoid substring conflicts
sorted_maps = sorted(MAPPING.items(), key=lambda x: -len(x[0]))

def apply_mapping_to_para(p):
    """Apply MAPPING to a paragraph's citations, longest key first."""
    combined = para_text(p)
    if '[' not in combined:
        return False
    changed = False
    for old_n, new_n in sorted_maps:
        if old_n == new_n:
            continue
        old_str = f'[{old_n}]'
        new_str = f'[{new_n}]'
        if old_str in para_text(p):  # re-check each time
            if replace_in_para(p, old_str, new_str):
                changed = True
    return changed

print(f"\n[Phase 3] Applying citation renumbering (body only)…")

changed = 0
for i, p in enumerate(paras):
    if 756 <= i <= 784:
        continue
    if apply_mapping_to_para(p):
        changed += 1

print(f"  Modified {changed} paragraphs ✓")

# ══════════════════════════════════════════════════════════════
# PHASE 3b: Replace temp tokens with final numbers
# ══════════════════════════════════════════════════════════════

TOKENS = {'__ISO__': '2', '__ANSI__': '13', '__NODE__': '22'}
for p in paras:
    combined = para_text(p)
    for tok, num in TOKENS.items():
        old_str = f'[{tok}]'
        new_str = f'[{num}]'
        if old_str in para_text(p):
            replace_in_para(p, old_str, new_str)

print(f"[Phase 3b] Tokens → final numbers ✓")

# ══════════════════════════════════════════════════════════════
# PHASE 4: Verify
# ══════════════════════════════════════════════════════════════

print(f"\n[Phase 4] Verification…")

cite_re = re.compile(r'\[(\d+)\]')
body_cites = []
for i, p in enumerate(paras):
    if 756 <= i <= 784 or i >= 785:
        continue
    t = para_text(p)
    if 'LISTA DE FIGURAS' in t or 'LISTA DE TABLAS' in t:
        continue
    for m in cite_re.findall(t):
        body_cites.append((i, m))

non_digit = [(i, c) for i, c in body_cites if not c.isdigit()]
if non_digit:
    print(f"  WARNING: non-digit: {non_digit}")
else:
    print(f"  All body citations numeric ✓")

body_nums = set(int(c) for _, c in body_cites if c.isdigit())
print(f"  Body citations ({len(body_nums)}): {sorted(body_nums)}")

ref_nums = []
for i in range(757, 785):
    t = para_text(paras[i])
    m = re.findall(r'\[(\d+)\]', t)
    if m:
        ref_nums.append(int(m[0]))
    else:
        print(f"  WARNING: ref para {i} missing header: {t[:80]}")

print(f"  Reference sequence: {ref_nums}")

uncited = set(ref_nums) - body_nums
missing = body_nums - set(ref_nums)
if not uncited and not missing:
    print(f"  ✅ Body citations and references match perfectly")
else:
    if uncited: print(f"  WARNING: uncited: {sorted(uncited)}")
    if missing: print(f"  WARNING: no ref: {sorted(missing)}")

# ══════════════════════════════════════════════════════════════
# PHASE 5: Write back (lxml preserves namespace prefixes)
# ══════════════════════════════════════════════════════════════

print(f"\n[Phase 5] Writing modified DOCX…")

modified_bytes = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=False)

tmp = DOCX + ".tmp"
with ZipFile(tmp, 'w', ZIP_DEFLATED) as zout:
    with ZipFile(BACKUP) as zin:
        for name in zin.namelist():
            zout.writestr(name, modified_bytes if name == 'word/document.xml' else zin.read(name))

shutil.move(tmp, DOCX)
print(f"  Written to {DOCX}")
print(f"\n✓ Done!")
