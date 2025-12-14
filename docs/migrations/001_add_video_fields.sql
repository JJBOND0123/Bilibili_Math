-- 为 videos 表新增分析/训练字段（可重复执行）
-- 用法：
-- 1) 先选择数据库：USE bilibili_math_db;
-- 2) 再执行本文件
--
-- 说明：
-- - MySQL 某些版本不支持 ADD COLUMN IF NOT EXISTS，这里用 information_schema 做“存在性判断”，确保可重复执行。
-- - 也可在爬虫参数里设置 auto_migrate=true，让爬虫自动检测并补齐缺失字段（但仍建议先手动迁移一次）。

SET @db := DATABASE();

-- aid
SET @col := 'aid';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `aid` BIGINT NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- video_url
SET @col := 'video_url';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `video_url` VARCHAR(255) NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- desc
SET @col := 'desc';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `desc` TEXT NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- like_count
SET @col := 'like_count';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `like_count` INT NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- coin_count
SET @col := 'coin_count';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `coin_count` INT NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- share_count
SET @col := 'share_count';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `share_count` INT NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- tag_names
SET @col := 'tag_names';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `tag_names` VARCHAR(1000) NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- source_keyword
SET @col := 'source_keyword';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `source_keyword` VARCHAR(255) NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- bili_tid
SET @col := 'bili_tid';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `bili_tid` INT NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- bili_tname
SET @col := 'bili_tname';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `bili_tname` VARCHAR(100) NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- crawl_time
SET @col := 'crawl_time';
SELECT COUNT(*) INTO @exists FROM information_schema.columns
WHERE table_schema = @db AND table_name = 'videos' AND column_name = @col;
SET @sql := IF(@exists = 0, 'ALTER TABLE `videos` ADD COLUMN `crawl_time` DATETIME NULL;', 'SELECT 1;');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
