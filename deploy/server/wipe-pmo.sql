-- Factory-reset the PMO console database: all business data and integration
-- settings go away; only the console login accounts (users) and the schema
-- version marker stay.
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE requirement_git_links;
TRUNCATE TABLE ai_inspections;
TRUNCATE TABLE weekly_snapshots;
TRUNCATE TABLE sync_logs;
TRUNCATE TABLE risks;
TRUNCATE TABLE requirements;
TRUNCATE TABLE external_projects;
TRUNCATE TABLE projects;
SET FOREIGN_KEY_CHECKS = 1;
DELETE FROM system_settings;
SELECT 'projects' t, COUNT(*) n FROM projects
UNION ALL SELECT 'requirements', COUNT(*) FROM requirements
UNION ALL SELECT 'external', COUNT(*) FROM external_projects
UNION ALL SELECT 'settings', COUNT(*) FROM system_settings
UNION ALL SELECT 'users', COUNT(*) FROM users;
