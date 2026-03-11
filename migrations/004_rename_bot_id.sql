-- Rename recall_bot_id to bot_id to match ORM model
ALTER TABLE meetings RENAME COLUMN recall_bot_id TO bot_id;
