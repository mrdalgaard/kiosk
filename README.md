# AASvK Kiosk System

AASvK Kiosk System er en webbaseret applikation, specielt designet til at køre fuldskærm på en 10" tablet i klubbens lokaler. Systemet er udviklet med to primære formål:
1. **Kiosk**: At gøre det hurtigt, nemt og enkelt for klubbens medlemmer at købe varer.
2. **Greenteam**: At tilbyde en overskuelig løsning til at registrere græsklipning og tracke vedligehold af maskinparken.

## Funktioner

- **Hurtigt Køb**: En intuitiv brugergrænseflade designet specielt til touchskærme, hvor medlemmer kan tilføje varer til en indkøbskurv og gennemføre køb på få sekunder.
- **Græsklipning**: Registrering af hvilke sektioner og hvor meget græs, der er klippet.
- **Maskinvedligehold**: Dynamisk system til at beregne driftstimer på udstyrsdele (f.eks. kraftoverføringsaksler og smørepunkter). Systemet giver et letlæseligt visuelt overblik, advarer når service er påkrævet, og understøtter både hurtige skiftedage og timetal, der går i minus.
- **Admin Panel**: Administratorer kan håndtere brugere, produkter, opdatere priser og overvåge logbøger og vedligeholdelsesintervaller.

## Teknisk Stack

- **Backend**: Python 3.x med [Flask](https://flask.palletsprojects.com/) frameworket.
- **Database**: PostgreSQL til robust datalagring, integreret via `psycopg`.
- **Frontend**: HTML5, Vanilla JavaScript, og Vanilla CSS for at sikre maksimal hastighed uden unødvendige afhængigheder. Responsivt kodet mod tablets.
- **Containerisering**: Docker og Docker Compose til at styre applikationens og databasens miljøkonfigurationer.

## Opsætning og Kørsel (Lokal Udvikling & Produktion)

Applikationen er bygget til at blive afviklet via Docker, hvilket sikrer, at alt kører ens uanset host-maskinen.

### 1. Klargøring af miljø
Start med at opsætte dine miljøvariabler:
```bash
cp .env.example .env
```
Åbn `.env` filen og tilpas databaseadgangskoder og session keys, hvis det er nødvendigt.

### 2. Start applikationen
For at bygge og starte applikationen bruges Docker Compose:
```bash
docker compose up -d --build
```

### 3. Første kørsel (Database Setup)
Når containerne kører, skal du konfigurere den tomme database med de korrekte tabeller og indsætte startdata (seed data for produkter og vedligeholdsintervaller).

Indlæs skema:
```bash
docker exec -i kiosk-db-1 psql -U KantinePOS -d KantinePOS < kiosk/schema.sql
```

Indsæt standard data (kun til lokal test):
```bash
docker exec -i kiosk-db-1 psql -U KantinePOS -d KantinePOS < seed.sql
```

Systemet er nu tilgængeligt i browseren på: `http://localhost:5000`

### 4. Public App (Read-Only)
Der er tilføjet en separat public status app (`kiosk-public`) som standard er konfigureret til port 5001. Denne instans kræver ikke login, og giver udelukkende en læseadgang (read-only) for øget sikkerhed. Processen er:

1. Opret en adskilt miljøfil (som du kan tilpasse med ny adgangskode efter eget valg for den offentlige adgang):
```bash
cp .env.public.example .env.public
```

2. Skab den specifikke read-only bruger i databasen:
```bash
cat setup_public_user.sql | docker exec -i kiosk-db-1 psql -U KantinePOS -d KantinePOS
```

3. Aktiver i Docker Compose:
Sørg for at fjerne kommentarerne (`#`) ud for `public_app`-sektionen i din `compose.yaml` fil (se `compose.example.yaml` for reference), hvorefter du kører `docker compose up -d`. Public applikationen er derefter tilgængelig på: `http://localhost:5001`

### Lokal kørsel udenfor Docker
Både den primære kiosk-app og public-appen kan køres direkte lokalt (ved f.eks. test og udvikling). Begge apps indlæser nu automatisk henholdsvis deres `.env` og `.env.public` filer.
For at undgå port-konflikter kan du angive en specifik port som det første argument:
```bash
python run.py 5010
python public_status/app.py 5011
```

## Fejlfinding (Troubleshooting)

* **Ændringer afspejles ikke**: Hvis du har lavet ændringer i koden lokalt, kræver genstart af applikationen ofte, at containeren genbygges for at de nye filer inkluderes: `docker compose up --build -d`.
* **Database Migrationer**: Hvis en kolonne tilføjes i et nyt commit, sikr dig at de eksisterende tabeller er afstemt, eller i værste fald kør `docker compose down -v` for at nulstille databasen og derefter starte på ny med trin 3 (Bemærk, at en `-v` sletter al produktionsdata).

## Tests

Projektet bruger `pytest` til at validere applikationens logik, databasereturneringer og frontend-komponenter.

En scripts-fil er inkluderet for nemt at køre testpakken internt i Docker-containeren under de helt korrekte forudsætninger. 
For at køre samtlige tests, brug:
```bash
./run_tests.sh
```
