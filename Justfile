install:
    #!/usr/bin/env python3
    import shutil, subprocess
    from pathlib import Path
    cmd = ["uv", "sync", "--extra", "dev"] if shutil.which("uv") else ["pip", "install", "-e", ".[dev]"]
    subprocess.run(cmd, check=True)
    if not Path(".env").exists():
        shutil.copy(".env.example", ".env")
        print("⚠️  .env créé — renseignez DEEZER_USER_ID et LASTFM_API_KEY")

run:
    deezerboy app

export:
    deezerboy export

stats:
    deezerboy stats

lint:
    ruff check src/

clean:
    #!/usr/bin/env python3
    import shutil
    from pathlib import Path
    for p in Path(".").rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    for p in Path(".").rglob("*.pyc"):
        p.unlink(missing_ok=True)
    print("✅ Nettoyage terminé")
