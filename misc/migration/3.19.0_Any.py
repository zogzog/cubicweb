sql('DROP TABLE "deleted_entities"')
sql('ALTER TABLE "entities" DROP COLUMN "mtime"')
sql('ALTER TABLE "entities" DROP COLUMN "source"')

