"""Analyze Apollo Contacts Export to extract real-world email patterns and their frequency."""
import csv
import re
import sys
from collections import Counter

csv.field_size_limit(sys.maxsize)

CSV_PATH = r"e:\email-enrichment\email-enrichment-puppet\tests\fixtures\csv\apollo-contacts-export (1).csv"

def classify_pattern(first_name: str, last_name: str, email: str, domain: str) -> str:
    """Classify the email pattern based on first/last name vs local part."""
    local_part = email.split("@")[0].lower()
    fn = first_name.lower().strip()
    ln = last_name.lower().strip()
    fi = fn[0] if fn else ""
    li = ln[0] if ln else ""
    
    # Check all known patterns
    checks = [
        (f"{fn}.{ln}", "first.last"),
        (f"{fn}{ln}", "firstlast"),
        (f"{fn}_{ln}", "first_last"),
        (f"{fn}-{ln}", "first-last"),
        (f"{fi}{ln}", "f.last (no dot)"),
        (f"{fi}.{ln}", "f.last"),
        (f"{fn}.{li}", "first.l"),
        (f"{fn}{li}", "firstl"),
        (f"{fn}", "first"),
        (f"{ln}", "last"),
        (f"{ln}.{fn}", "last.first"),
        (f"{ln}{fn}", "lastfirst"),
        (f"{ln}_{fn}", "last_first"),
        (f"{ln}.{fi}", "last.f"),
        (f"{ln}{fi}", "lastf"),
        (f"{fi}_{ln}", "f_last"),
        (f"{fi}-{ln}", "f-last"),
        (f"{fn}.{ln}1", "first.last1"),
        (f"{fn}.{ln}2", "first.last2"),
        (f"{fi}{ln}1", "flast1"),
        (f"{fn}1", "first1"),
        (f"{fn}2", "first2"),
        (f"{ln}.{fn[0]}" if fn else "", "last.fi"),
        # Swapped first/last (common in Indian names in Apollo)
        (f"{ln}.{fn}", "last.first"),
    ]
    
    for pattern_email, pattern_name in checks:
        if pattern_email and local_part == pattern_email:
            return pattern_name
    
    # Try nickname/abbreviation matching
    if "." in local_part:
        parts = local_part.split(".")
        if len(parts) == 2:
            p1, p2 = parts
            # Check if parts are substrings
            if fn.startswith(p1) and ln.startswith(p2):
                return f"first_abbrev.last_abbrev ({p1}.{p2})"
            if ln.startswith(p1) and fn.startswith(p2):
                return f"last_abbrev.first_abbrev ({p1}.{p2})"
    
    return f"UNKNOWN ({local_part} | fn={fn} ln={ln})"


results = []
pattern_counter = Counter()
pattern_examples = {}

with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        first = row.get("First Name", "").strip()
        last = row.get("Last Name", "").strip()
        email = row.get("Email", "").strip()
        company = row.get("Company Name", "").strip()
        status = row.get("Email Status", "").strip()
        website = row.get("Website", "").strip()
        
        if not first or not last or not email or "@" not in email:
            continue
        
        domain = email.split("@")[1]
        pattern = classify_pattern(first, last, email, domain)
        pattern_counter[pattern] += 1
        
        if pattern not in pattern_examples:
            pattern_examples[pattern] = []
        if len(pattern_examples[pattern]) < 3:
            pattern_examples[pattern].append(f"  {first} {last} -> {email} ({company})")
        
        results.append({
            "first": first,
            "last": last,
            "email": email,
            "company": company,
            "domain": domain,
            "pattern": pattern,
            "status": status,
            "website": website,
        })

print(f"\n{'='*80}")
print(f"APOLLO DATASET ANALYSIS: {len(results)} verified contacts")
print(f"{'='*80}\n")

print(f"{'Pattern':<35} {'Count':>6} {'%':>7}")
print(f"{'-'*35} {'-'*6} {'-'*7}")

total = len(results)
for pattern, count in pattern_counter.most_common():
    pct = (count / total) * 100
    print(f"{pattern:<35} {count:>6} {pct:>6.1f}%")
    for ex in pattern_examples[pattern]:
        print(f"    {ex}")

print(f"\n{'='*80}")
print(f"DOMAIN vs WEBSITE ANALYSIS (Company Domain Accuracy)")
print(f"{'='*80}\n")

domain_mismatches = 0
for r in results:
    website = r["website"].lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
    email_domain = r["domain"].lower()
    if website and website != email_domain:
        domain_mismatches += 1
        if domain_mismatches <= 10:
            print(f"  Company: {r['company']}")
            print(f"    Website:      {website}")
            print(f"    Email Domain: {email_domain}")
            print()

print(f"\nTotal mismatches (website != email domain): {domain_mismatches}/{total}")
