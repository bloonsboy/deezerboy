#!/bin/bash
# Lancer l'export CSV rapidement

echo ""
echo "🎵 DeezerBoy - Export CSV"
echo "========================"
echo ""

# Activer l'environnement
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "⚠️  Environment non trouvé. Lancez 'uv sync' d'abord"
    exit 1
fi

# Lancer l'export
python export_quick.py
