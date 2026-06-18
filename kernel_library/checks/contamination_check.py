import hashlib, re, sys
from pathlib import Path

def normalize(text):
    text = re.sub(r"--.*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"\s+", "", text.lower())
    return text

def digest(path):
    return hashlib.sha256(normalize(Path(path).read_text(errors="ignore")).encode()).hexdigest()

def main(kernels_dir, eval_dir):
    kernels = list(Path(kernels_dir).rglob("*.vhd")) + list(Path(kernels_dir).rglob("*.v"))
    evals = list(Path(eval_dir).rglob("*.vhd")) + list(Path(eval_dir).rglob("*.v"))
    kh = {digest(p): p for p in kernels}
    found = False
    for e in evals:
        h = digest(e)
        if h in kh:
            print(f"EXACT_MATCH: eval={e} kernel={kh[h]}")
            found = True
    if not found:
        print("No exact normalized SHA-256 matches found.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python contamination_check.py kernel_library/hdl evaluation_refs/")
        raise SystemExit(2)
    main(sys.argv[1], sys.argv[2])
