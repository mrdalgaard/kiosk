# AASvK Kiosk System

En webbaseret PWA designet til at køre fuldskærm på en 10" tablet i klubbens lokaler.

## Funktioner

### Kiosk
- Intuitiv touchvenlig brugergrænseflade til hurtige varekøb.
- Asynkron indkøbskurv — tilføj og fjern varer uden sideopdatering.
- Købshistorik pr. medlem.
- Admin panel til håndtering af brugere, produkter og priser.

### Greenteam
- Registrering af græsklipning pr. sektion.
- Dynamisk beregning af driftstimer og vedligeholdelsesintervaller.
- Visuel advarsel når service er påkrævet.
- Offentlig read-only statusside (separat app, port 5001).

## Teknisk Stack

| Komponent | Teknologi |
|---|---|
| Backend | Python / Flask |
| Database | PostgreSQL via `psycopg` |
| Frontend | HTML5, Vanilla JS, Vanilla CSS |
| Container | Docker / Docker Compose |

## Projektstruktur

```
├── Dockerfile              # Kiosk app
├── Dockerfile.public       # Public status app
├── compose.yaml
├── kiosk/                  # Hovedapplikation
├── public_status/          # Read-only statusside
├── scripts/                # SQL seeds, migrationer, test-script
├── tests/                  # pytest test suite
└── data/images/            # Produktbilleder (volume mount)
```

## Opsætning

### 1. Klargør miljøvariabler
```bash
cp .env.example .env
cp .env.public.example .env.public
```
Tilpas databaseadgangskoder og session keys i `.env` efter behov.

### 2. Konfigurer Docker Compose
Kopiér og tilpas `compose.yaml` ud fra eksempelfilen:
```bash
cp compose.example.yaml compose.yaml
```
Filen indeholder følgende valgfrie sektioner, som kan aktiveres ved at fjerne kommentarerne (`#`):
- **`public_app`** — Read-only offentlig statusside (port 5001). Kræver `.env.public`.
- **`db`** — Lokal PostgreSQL-instans. Udelad hvis du bruger en ekstern database.
- **`depends_on: db`** — under `app`-sektionen. Aktiver hvis `db`-servicen bruges.

### 3. Start applikationen
```bash
docker compose up -d --build
```

### 4. Første kørsel (Database)
Applikationen opretter automatisk tabeller og views. Indsæt testdata:
```bash
docker exec -i kiosk-db-1 psql -U KioskPOS -d KioskPOS < scripts/seed-testdata.sql
```

Opret read-only databasebruger til den offentlige app:
```bash
cat scripts/setup_public_user.sql | docker exec -i kiosk-db-1 psql -U KioskPOS -d KioskPOS
```

Kiosk: `http://localhost:5000` · Public status: `http://localhost:5001`

## e-conomic Integration

Applikationen integrerer med [e-conomic](https://www.e-conomic.dk/) REST API til automatisk bogføring af salg og synkronisering af kundelisten.

### Opsætning af API-adgang
1. Log ind på [e-conomic Developer](https://secure.e-conomic.com/developer).
2. Opret en ny app (eller brug en eksisterende) — dette giver dig en **App Secret Token**.
3. Under den oprettede app, tilknyt den til dit e-conomic-agreement — dette genererer en **Agreement Grant Token**. Se https://www.e-conomic.com/developer/connect for mere information.
4. Angiv begge tokens i `.env`:
```env
ECO_GRANT_TOKEN=dit_grant_token
ECO_SECRET_TOKEN=dit_secret_token
ECO_PRODUCT_ID=8000
```
`ECO_PRODUCT_ID` skal matche det produktnummer i e-conomic, som bruges til at bogføre salgslinjer.

### Brugersynkronisering
Applikationen synkroniserer også automatisk kundelisten fra e-conomic. Kunder hentes baseret på konfigurerede kundegrupper (`CUSTOMER_GROUPS` i `config.py`) og upserted i den lokale database. Kunder der fjernes fra e-conomic markeres som slettet lokalt.

### Lokal kørsel uden Docker
```bash
python kiosk/run.py 5010
python public_status/app.py 5011
```

## Tests
```bash
./scripts/run_tests.sh
```

## Fejlfinding

- **Kodeændringer vises ikke?** Genbyg containeren: `docker compose up --build -d`
- **Databaseændringer?** Nulstil med `docker compose down -v` og kør seed igen (sletter al data).
