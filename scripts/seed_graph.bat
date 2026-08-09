@echo off
echo Seeding Neo4j Graph Database to production container...
if not exist "neo4j_backup.cypher" (
    echo Error: neo4j_backup.cypher not found. Please run backup_graph.bat first.
    exit /b 1
)
echo Copying backup file to production container...
docker cp ./neo4j_backup.cypher farmmate_neo4j_prod:/var/lib/neo4j/import/backup.cypher
echo Executing cypher script...
docker exec farmmate_neo4j_prod cypher-shell -u neo4j -p farmmatepassword -f /var/lib/neo4j/import/backup.cypher
echo Seeding completed successfully.
