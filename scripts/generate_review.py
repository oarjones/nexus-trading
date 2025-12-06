from pathlib import Path

artifacts_dir = Path(r"C:\Users\PC\.gemini\antigravity\brain\65ba0bc2-e52c-4cc2-851a-a27a809395b2")
files = [
    "src/ml/interfaces.py",
    "src/ml/exceptions.py",
    "src/ml/models/hmm_regime.py",
    "src/ml/models/rules_baseline.py",
    "src/ml/factory.py",
    "config/ml_models.yaml",
    "mcp_servers/ml_models/tools/regime.py",
    "mcp_servers/ml_models/tools/model_info.py",
    "mcp_servers/ml_models/server.py"
]

out_file = artifacts_dir / "phase_a2_code_review.md"
with open(out_file, "w", encoding="utf-8") as f:
    f.write("# Phase A2 Code Review\n\n")
    f.write("Consolidated source code for Phase A2 components.\n\n")
    for file_path in files:
        p = Path(file_path)
        if p.exists():
            f.write(f"## {file_path}\n\n")
            ext = p.suffix.lstrip(".")
            f.write(f"```{ext}\n")
            f.write(p.read_text(encoding="utf-8"))
            f.write("\n```\n\n")
        else:
            f.write(f"## {file_path} (MISSING)\n\n")
print(f"Created {out_file}")
