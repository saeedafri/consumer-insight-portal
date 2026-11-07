-- What each role may use, as the super admin set it on the Access screen (frontend/src/screens/Access.tsx →
-- PUT /api/v1/admin/roles/<role>, api/main.py). Read by shared/core/access.py managed_features (cached 30 s): a role
-- listed here gets exactly these features (menus), over its package's (config/access.yml tiers). The super admin
-- always has everything and is never listed. Created by the API on the first save, or by scripts/init_db.py.
CREATE TABLE IF NOT EXISTS cip_role_access (
  role        VARCHAR(255)  NOT NULL              COMMENT 'whose menus: a role (analyst), a client (client:acme) or a person (person:ana@acme.com)',
  features    TEXT          NOT NULL              COMMENT 'JSON list of the features (menus) the role may use',
  updated_by  VARCHAR(255)  NOT NULL              COMMENT 'who saved it (the super admin)',
  updated_at  DATETIME      NOT NULL,
  PRIMARY KEY (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Each role''s menus, set by the super admin';
