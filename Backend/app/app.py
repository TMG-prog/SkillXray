import argparse
import os
import sys
import pandas as pd
import skillxray as sx  # loads the extractor, SBERT, ESCO data and the frozen profiles once, at start-up

# Configure pandas to show full columns when printing tables locally
pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", 1000)

ROLES = sx.available_roles()
DEFAULT_ROLE = "it support" if "it support" in ROLES else (ROLES[0] if ROLES else None)
MAX_CV_WORDS = 6000  # keeps processing fast and prevents excessive memory usage


def _cv_text(path, pasted):
    if pasted and pasted.strip():
        return pasted
    if path:
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        return sx.read_resume_file(path)
    return ""


def analyse(cv_path=None, cv_pasted=None, role=None):
    if not role:
        raise ValueError("Please specify a target role.")
    if role not in ROLES:
        raise ValueError(f"Role '{role}' is invalid. Choose from: {', '.join(ROLES)}")

    try:
        text = _cv_text(cv_path, cv_pasted)
    except Exception as e:
        raise RuntimeError(
            f"Could not read the file/text: {type(e).__name__} - {e}. "
            "Try passing a valid .docx, .pdf, .txt file path or direct text."
        )

    n_words = len(text.split())
    if n_words < 30:
        raise ValueError(
            "Almost no text was found (<30 words). A scanned (image-only) PDF needs OCR first."
        )
    if n_words > MAX_CV_WORDS:
        text = " ".join(text.split()[:MAX_CV_WORDS])

    res = sx.score_cv(text, role)
    tab, prof = res["table"], res["profile"]

    notes = []
    if n_words < 150:
        notes.append(
            f"Only {n_words} words were extracted from the CV, so the score will be low whatever the model does."
        )
    if prof.get("source") == "static":
        notes.append(
            f"Using the built-in static profile ({prof.get('reason')}), not a recent job-market snapshot."
        )

    unseen = [
        l
        for l in tab["esco_label"]
        if l in (getattr(sx.NS_SPANS, "missing", set()) | getattr(sx.NS_WIN, "missing", set()))
    ]
    if unseen:
        notes.append(
            f"{len(set(unseen))} requirement(s) had no saved calibration statistics "
            "and used default values, so their match is less reliable."
        )

    src = f"{prof.get('source')}" + (f" release {prof['release']}" if prof.get("release") else "")
    summary = (
        f"==================================================\n"
        f"  READINESS SCORE: {res['readiness'] * 100:.0f}%\n"
        f"==================================================\n"
        f"Covers {int(tab['covered'].sum())} of {len(tab)} skills required for target role '{role}'.\n"
        f"Profile Source: {src} (built from {prof.get('n_postings') or '?'} postings).\n"
    )

    if notes:
        summary += "\nNotes:\n" + "".join(f" - {n}\n" for n in notes)

    gaps = (
        tab.loc[~tab["covered"]]
        .sort_values("weight", ascending=False)
        .assign(importance=lambda d: (d["weight"] * 100).round(1))
        [["esco_label", "importance", "gap_confidence", "closest_evidence"]]
        .rename(
            columns={
                "esco_label": "Missing Skill",
                "importance": "Importance (%)",
                "gap_confidence": "Gap Confidence",
                "closest_evidence": "Closest CV Evidence",
            }
        )
        .reset_index(drop=True)
    )

    have = (
        tab.loc[tab["covered"]]
        .sort_values("weight", ascending=False)
        [["esco_label", "reason", "closest_evidence"]]
        .rename(
            columns={
                "esco_label": "Skill Found",
                "reason": "Match Reason",
                "closest_evidence": "CV Evidence",
            }
        )
        .reset_index(drop=True)
    )

    return summary, gaps, have


def main():
    parser = argparse.ArgumentParser(description="SkillXray Local CV Analysis CLI")
    parser.add_argument("--file", "-f", help="Path to CV file (.pdf, .docx, .txt)")
    parser.add_argument("--text", "-t", help="Raw CV text pasted directly")
    parser.add_argument(
        "--role",
        "-r",
        default=DEFAULT_ROLE,
        help=f"Target role name (Default: {DEFAULT_ROLE})",
    )
    parser.add_argument(
        "--list-roles", action="store_true", help="List all available roles and exit"
    )

    args = parser.parse_args()

    if args.list_roles:
        print("Available roles in SkillXray:")
        for r in ROLES:
            print(f" - {r}")
        sys.exit(0)

    if not args.file and not args.text:
        print("Error: Please specify either --file or --text.")
        print("Usage example: python script.py --file my_resume.pdf --role 'it support'")
        sys.exit(1)

    try:
        summary, gaps, have = analyse(
            cv_path=args.file, cv_pasted=args.text, role=args.role
        )

        print("\n" + summary + "\n")

        print("--- SKILL GAPS (MOST IMPORTANT FIRST) ---")
        if gaps.empty:
            print("No missing skills found!")
        else:
            print(gaps.to_string(index=False))

        print("\n--- SKILLS COVERED BY YOUR CV ---")
        if have.empty:
            print("No matching skills found in CV.")
        else:
            print(have.to_string(index=False))

    except Exception as err:
        print(f"\n[Error]: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()