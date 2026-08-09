# Neo4j Graph Backup & Seed Scripts

These scripts are used to backup the local development Neo4j graph and seed it into the production environment.

## 1. Backup the local Graph Data
Make sure your development Docker containers are running (`docker-compose -f docker-compose.dev.yml up -d`).

### 🪟 On Windows
Open PowerShell or Command Prompt at the root of the project and run:
```powershell
.\scripts\backup_graph.bat
```

### 🐧 On Linux / Mac
Open your Terminal at the root of the project and run:
```bash
# Make the script executable (you only need to do this once)
chmod +x scripts/backup_graph.sh

# Run the script
./scripts/backup_graph.sh
```

## 2. Seed Data in Production
The backup step creates a `neo4j_backup.cypher` file in the root of the project. Make sure this file is present before seeding. Once the production containers are running (`docker-compose up -d`), execute the seeding script:

### 🪟 On Windows
```powershell
.\scripts\seed_graph.bat
```

### 🐧 On Linux / Mac
```bash
# Make the script executable (you only need to do this once)
chmod +x scripts/seed_graph.sh

# Run the script
./scripts/seed_graph.sh
```
