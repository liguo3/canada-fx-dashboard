# Canada Dashboard

Sito semplice per visualizzare il tasso di inflazione canadese e una previsione a 3 mesi.

## Avvio

1. Crea un ambiente Python (consigliato):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Installa le dipendenze:

```bash
pip install -r requirements.txt
```

3. Aggiorna i dati (opzionale ma consigliato):

```bash
python scripts/update_cpi.py
```

4. Avvia l'app Streamlit:

```bash
streamlit run app.py
```

## Cosa mostra

- Grafico storico dell'inflazione (CPI YoY)
- 3 barre che mostrano la previsione per i prossimi 3 mesi (basata sulla variazione media mensile)

